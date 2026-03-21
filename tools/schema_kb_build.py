"""
Workflow tool: full schema extraction + upload to a Dify knowledge base selected in the UI.

Target KB is a required dynamic-select (options from Dify ``list_datasets`` using provider credentials).
Output: only ``true`` or ``false``.
"""

import logging
import os
import sys
from collections.abc import Generator
from typing import Any

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dify_plugin import Tool
from dify_plugin.config.logger_format import plugin_logger_handler
from dify_plugin.entities import I18nObject, ParameterOption
from dify_plugin.entities.tool import ToolInvokeMessage

from provider.build_lm_db_schema_rag import build_schema_kb_from_credentials

# YAML parameter name (dynamic-select); value at invoke time = dataset UUID
_KNOWLEDGE_DATASET_PARAM = "knowledge_dataset"


def _datasets_to_parameter_options(
    api_uri: str,
    dataset_api_key: str,
    logger: logging.Logger,
    *,
    page_size: int = 50,
    max_pages: int = 40,
) -> list[ParameterOption]:
    """List datasets visible to the dataset API key; labels = human-readable names."""
    try:
        from core.dify.dify_client import KnowledgeBaseClient
    except ImportError:
        logger.error("KnowledgeBaseClient not available for dataset list")
        return []

    base = (api_uri or "").strip().rstrip("/")
    key = (dataset_api_key or "").strip()
    if not base or not key:
        return []

    client = KnowledgeBaseClient(api_key=key, base_url=base)
    options: list[ParameterOption] = []
    seen: set[str] = set()

    for page in range(1, max_pages + 1):
        try:
            resp = client.list_datasets(page=page, page_size=page_size)
            payload = resp.json()
        except Exception as e:
            logger.warning("list_datasets page=%s failed: %s", page, e)
            break

        rows = payload.get("data") or []
        if not rows:
            break

        for row in rows:
            did = row.get("id")
            if not did:
                continue
            sid = str(did)
            if sid in seen:
                continue
            seen.add(sid)
            name = (row.get("name") or sid).strip() or sid
            options.append(
                ParameterOption(
                    value=sid,
                    label=I18nObject(en_US=name),
                )
            )

        if len(rows) < page_size:
            break

    return options


class SchemaKbBuildTool(Tool):
    """Runs schema KB build; target dataset is chosen from Dify KB list (dynamic-select)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(plugin_logger_handler)

    def _fetch_parameter_options(self, parameter: str) -> list[ParameterOption]:
        if parameter != _KNOWLEDGE_DATASET_PARAM:
            return []
        creds = self.runtime.credentials
        return _datasets_to_parameter_options(
            creds.get("api_uri") or "",
            creds.get("dataset_api_key") or "",
            self.logger,
        )

    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        creds = self.runtime.credentials

        required = (
            creds.get("api_uri"),
            creds.get("dataset_api_key"),
            creds.get("db_type"),
            creds.get("db_name"),
        )
        if not all(required):
            yield self.create_text_message(text="false")
            return

        db_type = creds.get("db_type")
        if db_type != "sqlite":
            if not all(
                (
                    creds.get("db_host"),
                    creds.get("db_user"),
                    creds.get("db_password"),
                )
            ):
                yield self.create_text_message(text="false")
                return

        raw = tool_parameters.get(_KNOWLEDGE_DATASET_PARAM)
        ds_id = (raw if isinstance(raw, str) else str(raw or "")).strip()
        if not ds_id:
            yield self.create_text_message(text="false")
            return

        try:
            build_schema_kb_from_credentials(
                dict(creds),
                dataset_id=ds_id,
                dataset_name=None,
            )
            yield self.create_text_message(text="true")
        except Exception as e:
            self.logger.error("Schema KB build failed: %s", e, exc_info=True)
            yield self.create_text_message(text="false")
