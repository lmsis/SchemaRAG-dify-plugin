import copy
import logging
import os
import sys
import threading
import time
from typing import Any

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)  # add parent directory to path

from dify_plugin import ToolProvider
from dify_plugin.config.logger_format import plugin_logger_handler

from config import DatabaseConfig, DifyUploadConfig, LoggerConfig
from service.schema_builder import LmDbSchemaRagBuilder, ping_database_connection
from tools.sql_executer import SQLExecuterTool
from tools.text2sql import Text2SQLTool


def _truthy_credential_flag(raw: Any) -> bool:
    if raw is True:
        return True
    if raw is False or raw is None:
        return False
    if isinstance(raw, str):
        return raw.strip().lower() in ("1", "true", "yes", "on")
    return bool(raw)


def _background_kb_build(credentials: dict[str, Any]) -> None:
    """Runs full schema + Dify upload; must never raise to the HTTP layer."""
    log = logging.getLogger(f"{__name__}.background_kb")
    log.setLevel(logging.INFO)
    if not log.handlers:
        log.addHandler(plugin_logger_handler)

    log.info(
        "[provider] phase=background_kb_thread_started db=%r thread=%s",
        credentials.get("db_name"),
        threading.current_thread().name,
    )
    try:
        provider = LmDbSchemaRagProvider()
        provider._build_lm_db_schema_rag(credentials)
    except Exception:
        log.error(
            "[provider] phase=background_kb_thread_failed db=%r",
            credentials.get("db_name"),
            exc_info=True,
        )


class LmDbSchemaRagProvider(ToolProvider):
    """
    LM DB Schema RAG — tool provider (credentials validation + schema KB build).
    """

    def _get_default_port(self, db_type: str) -> int:
        """Default TCP port per database type."""
        port_mapping = {
            "mysql": 3306,
            "postgresql": 5432,
            "mssql": 1433,
            "oracle": 1521,
            "dameng": 5236,
            "doris": 9030,
        }
        return port_mapping.get(db_type, 3306)

    def _database_config_from_credentials(
        self, credentials: dict[str, Any]
    ) -> DatabaseConfig:
        db_type = credentials.get("db_type")
        return DatabaseConfig(
            type=db_type,
            host=credentials.get("db_host"),
            port=credentials.get("db_port"),
            user=credentials.get("db_user"),
            password=credentials.get("db_password"),
            database=credentials.get("db_name"),
        )

    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        """
        Validate the credentials and build schema knowledge base for RAG.
        """
        api_uri = credentials.get("api_uri")
        dataset_api_key = credentials.get("dataset_api_key")
        db_type = credentials.get("db_type")
        db_host = credentials.get("db_host")
        db_user = credentials.get("db_user")
        db_password = credentials.get("db_password")
        db_name = credentials.get("db_name")

        if not api_uri:
            raise ValueError("API URI is required")

        if not dataset_api_key:
            raise ValueError("Dataset API key is required")

        if not db_type:
            raise ValueError("Database type is required")

        if db_type == "sqlite":
            if not db_name:
                raise ValueError("Database name (file path) is required for SQLite")
        elif db_type == "doris":
            if not db_host:
                raise ValueError("Doris database host is required")
            if not db_user:
                raise ValueError("Doris database user is required")
            if not db_password:
                raise ValueError("Doris database password is required")
            if not db_name:
                raise ValueError("Doris database name is required")
        else:
            if not db_host:
                raise ValueError("Database host is required")

            if not db_user:
                raise ValueError("Database user is required")

            if not db_password:
                raise ValueError("Database password is required")

            if not db_name:
                raise ValueError("Database name is required")

        log = logging.getLogger(__name__)
        log.setLevel(logging.INFO)
        if not log.handlers:
            log.addHandler(plugin_logger_handler)

        background = _truthy_credential_flag(credentials.get("kb_build_in_background"))

        if background:
            db_config = self._database_config_from_credentials(credentials)
            try:
                ping_database_connection(db_config)
            except Exception as e:
                log.error(
                    "[provider] phase=quick_db_ping_failed db=%r error=%s",
                    db_name,
                    e,
                    exc_info=True,
                )
                raise ValueError(
                    f"[provider] phase=quick_db_ping database={db_name!r}: {e}"
                ) from e

            cred_copy = copy.deepcopy(credentials)
            thread = threading.Thread(
                target=_background_kb_build,
                args=(cred_copy,),
                name="lm-schema-kb-build",
                daemon=True,
            )
            thread.start()
            log.info(
                "[provider] phase=kb_build_deferred db=%r — full schema+upload running "
                "in background thread %s; validation returned OK",
                db_name,
                thread.name,
            )
            return

        self._build_lm_db_schema_rag(credentials)

    def _build_lm_db_schema_rag(self, credentials: dict[str, Any]) -> None:
        """
        Build schema RAG knowledge base using the provided credentials.
        """
        try:

            db_type = credentials.get("db_type")

            db_config = self._database_config_from_credentials(credentials)

            logger_config = LoggerConfig(log_level="INFO")
            log = logging.getLogger(__name__)
            log.setLevel(logging.INFO)
            if not log.handlers:
                log.addHandler(plugin_logger_handler)

            dify_config = DifyUploadConfig(
                api_key=credentials.get("dataset_api_key"),
                base_url=credentials.get("api_uri"),
                indexing_technique="high_quality",
                permission="all_team_members",
                process_mode="custom",
                max_tokens=4000,
            )

            tables_name = credentials.get("tables_name", "")
            include_tables = None
            if tables_name and tables_name.strip():
                include_tables = [
                    table.strip()
                    for table in tables_name.split(",")
                    if table.strip()
                ]
                logging.info(
                    "[provider] phase=kb_scope subset_tables=%s", include_tables
                )
            else:
                logging.info("[provider] phase=kb_scope all_tables_in_database")

            t_build = time.monotonic()
            logging.info(
                "[provider] phase=kb_build_start db_type=%s database=%r",
                db_type,
                db_config.database,
            )
            builder = LmDbSchemaRagBuilder(
                db_config, logger_config, dify_config, include_tables
            )

            try:
                schema_content = builder.generate_dictionary()

                markers = schema_content.count("#") if schema_content else 0
                logging.info(
                    "[provider] phase=dictionary_ready lines_with_hash=%d approx_size_chars=%d",
                    markers,
                    len(schema_content) if schema_content else 0,
                )

                dataset_name = f"{db_config.database}_schema"
                builder.upload_text_to_dify(dataset_name, schema_content)
                logging.info(
                    "[provider] phase=kb_build_complete dataset_name=%r total_duration_s=%.2f",
                    dataset_name,
                    time.monotonic() - t_build,
                )

            except Exception as e:
                logging.error(
                    "[provider] phase=kb_build_failed database=%r after_s=%.2f error=%s",
                    db_config.database,
                    time.monotonic() - t_build,
                    e,
                    exc_info=True,
                )
                raise ValueError(
                    f"[provider] phase=kb_build_failed database={db_config.database!r}: {e}"
                ) from e
            finally:
                builder.close()

        except ValueError:
            raise
        except Exception as e:
            logging.error(
                "[provider] phase=credential_or_build error=%s", e, exc_info=True
            )
            raise ValueError(
                f"[provider] phase=credential_or_build db={credentials.get('db_name')!r}: {e}"
            ) from e

    def get_tools(self):
        """Return available tools."""
        return [Text2SQLTool, SQLExecuterTool]
