import logging
import os
import sys
import time
from typing import Any

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)  # add parent directory to path

from dify_plugin import ToolProvider
from tools.text2sql import Text2SQLTool
from tools.sql_executer import SQLExecuterTool
from config import DatabaseConfig, LoggerConfig, DifyUploadConfig
from service.schema_builder import LmDbSchemaRagBuilder
from dify_plugin.config.logger_format import plugin_logger_handler


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

        self._build_lm_db_schema_rag(credentials)

    def _build_lm_db_schema_rag(self, credentials: dict[str, Any]) -> None:
        """
        Build schema RAG knowledge base using the provided credentials.
        """
        try:

            db_type = credentials.get("db_type")

            if db_type == "doris":
                db_config = DatabaseConfig(
                    type=db_type,
                    host=credentials.get("db_host"),
                    port=credentials.get("db_port"),
                    user=credentials.get("db_user"),
                    password=credentials.get("db_password"),
                    database=credentials.get("db_name"),
                )
            else:
                db_config = DatabaseConfig(
                    type=db_type,
                    host=credentials.get("db_host"),
                    port=credentials.get("db_port"),
                    user=credentials.get("db_user"),
                    password=credentials.get("db_password"),
                    database=credentials.get("db_name"),
                )

            logger_config = LoggerConfig(
                log_level="INFO"
            )
            log = logging.getLogger(__name__)
            log.setLevel(logging.INFO)
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
