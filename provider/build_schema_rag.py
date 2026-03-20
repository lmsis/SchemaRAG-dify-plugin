import os
from typing import Any
import sys
import logging
from venv import logger


sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)  # add parent directory to path

from dify_plugin import ToolProvider
from tools.text2sql import Text2SQLTool
from tools.sql_executer import SQLExecuterTool
from config import DatabaseConfig, LoggerConfig, DifyUploadConfig
from service.schema_builder import SchemaRAGBuilder
from dify_plugin.config.logger_format import plugin_logger_handler


class SchemaRAGBuilderProvider(ToolProvider):
    """
    Schema RAG Builder Provider
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
        Validate the credentials and build schema RAG
        """
        # Required credentials
        api_uri = credentials.get("api_uri")
        dataset_api_key = credentials.get("dataset_api_key")
        db_type = credentials.get("db_type")
        db_host = credentials.get("db_host")
        db_user = credentials.get("db_user")
        db_password = credentials.get("db_password")
        db_name = credentials.get("db_name")
        # build_rag = credentials.get("build_rag", True)

        # API parameters
        if not api_uri:
            raise ValueError("API URI is required")

        if not dataset_api_key:
            raise ValueError("Dataset API key is required")

        # Database parameters
        if not db_type:
            raise ValueError("Database type is required")

        # SQLite: only database path/name
        if db_type == "sqlite":
            if not db_name:
                raise ValueError("Database name (file path) is required for SQLite")
        elif db_type == "doris":
            # Doris: host, port, user, password, database
            if not db_host:
                raise ValueError("Doris database host is required")
            if not db_user:
                raise ValueError("Doris database user is required")
            if not db_password:
                raise ValueError("Doris database password is required")
            if not db_name:
                raise ValueError("Doris database name is required")
        else:
            # Other drivers: full connection fields
            if not db_host:
                raise ValueError("Database host is required")

            if not db_user:
                raise ValueError("Database user is required")

            if not db_password:
                raise ValueError("Database password is required")

            if not db_name:
                raise ValueError("Database name is required")

        self._build_schema_rag(credentials)
        # After validation, always build (build_rag toggle may be re-enabled later)
        # if build_rag:
        #     self._build_schema_rag(credentials)
        # else:
        #     logging.info("build_rag is False; skipping Schema RAG build")

    def _build_schema_rag(self, credentials: dict[str, Any]) -> None:
        """
        Build schema RAG using the provided credentials
        """
        try:

            # Database config
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

            # Logging
            logger_config = LoggerConfig(
                log_level="INFO"
            )
            logger = logging.getLogger(__name__)
            logger.setLevel(logging.INFO)
            logger.addHandler(plugin_logger_handler)
            
            # Dify upload settings
            dify_config = DifyUploadConfig(
                api_key=credentials.get("dataset_api_key"),
                base_url=credentials.get("api_uri"),
                indexing_technique="high_quality",
                permission="all_team_members",
                process_mode="custom",
                max_tokens=4000,
            )

            # Optional table filter
            tables_name = credentials.get("tables_name", "")
            include_tables = None
            if tables_name and tables_name.strip():
                include_tables = [table.strip() for table in tables_name.split(",") if table.strip()]
                logging.info(f"Building RAG for tables: {include_tables}")
            else:
                logging.info("Building RAG for all tables")

            # Builder
            builder = SchemaRAGBuilder(db_config, logger_config, dify_config, include_tables)

            try:
                schema_content = builder.generate_dictionary()

                table_count = schema_content.count("#") if schema_content else 0
                logging.info(f"Data dictionary generated ({table_count} table markers)")

                dataset_name = f"{db_config.database}_schema"
                builder.upload_text_to_dify(dataset_name, schema_content)
                logging.info("Uploaded to Dify knowledge base")

            except Exception as e:
                logging.error(f"Schema RAG build failed: {e}")
                raise ValueError(f"Schema RAG build failed: {str(e)}")
            finally:
                builder.close()

        except Exception as e:
            logging.error(f"Credential validation or build error: {e}")
            raise ValueError(f"Credential validation or build error: {str(e)}")

    def get_tools(self):
        """
        Return available tools
        """
        return [Text2SQLTool, SQLExecuterTool]
