"""
Workflow tool: full schema extraction + upload to a Dify dataset.

``dataset_id`` matches Text2SQL (string, form llm). Output: only ``true`` or ``false``.
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
from dify_plugin.entities.tool import ToolInvokeMessage

from provider.build_lm_db_schema_rag import build_schema_kb_from_credentials


class SchemaKbBuildTool(Tool):
    """Runs schema KB build; ``dataset_id`` is the same parameter style as Text2SQL."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(plugin_logger_handler)

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

        raw = tool_parameters.get("dataset_id")
        if isinstance(raw, str):
            ds_id = raw.split(",")[0].strip()
        else:
            ds_id = str(raw or "").strip()
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
