import os
import time
from typing import List, Optional
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)  # add parent directory to path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from core.m_schema.schema_engine import SchemaEngine

# Try to import Dameng SQLAlchemy dialect; registers if available
try:
    import sqlalchemy_dm  # noqa: F401
except ImportError:
    pass  # Dameng support is optional
from config import DatabaseConfig, DifyUploadConfig, LoggerConfig
from service.dify_service import DifyUploader
from utils import Logger, read_json


def sqlalchemy_engine_kwargs(db_type: str) -> dict:
    """SQLAlchemy engine kwargs by database type (shared: builder + quick ping)."""
    engine_args: dict = {
        "pool_pre_ping": True,
        "pool_recycle": 3600,
        "echo": False,
    }
    if db_type == "mysql" or db_type == "doris":
        engine_args["connect_args"] = {"charset": "utf8mb4"}
    elif db_type == "mssql":
        engine_args["connect_args"] = {"charset": "utf8"}
    elif db_type == "oracle":
        engine_args["connect_args"] = {"thick_mode": False}
    elif db_type == "dameng":
        engine_args["connect_args"] = {"encoding": "UTF-8"}
    return engine_args


def ping_database_connection(db_config: DatabaseConfig) -> None:
    """
    Open a connection and run SELECT 1 to verify credentials (fast path for provider validate).
    """
    engine = create_engine(
        db_config.get_connection_string(),
        **sqlalchemy_engine_kwargs(db_config.type),
    )
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    finally:
        engine.dispose()


class LmDbSchemaRagBuilder:
    """
    Orchestrates data dictionary generation and upload.
    Initialize with db_config, logger_config, dify_config objects, or use from_config_file.
    """

    def __init__(
        self,
        db_config: DatabaseConfig,
        logger_config: LoggerConfig,
        dify_config: Optional[DifyUploadConfig] = None,
        include_tables: Optional[List[str]] = None,
    ):
        if not isinstance(db_config, DatabaseConfig):
            raise TypeError("db_config must be a DatabaseConfig instance")
        if not isinstance(logger_config, LoggerConfig):
            raise TypeError("logger_config must be a LoggerConfig instance")
        if dify_config is not None and not isinstance(dify_config, DifyUploadConfig):
            raise TypeError("dify_config must be a DifyUploadConfig instance or None")
        self.db_config = db_config
        self.logger_config = logger_config
        self.dify_config = dify_config
        self.include_tables = include_tables
        self.logger_manager = Logger(self.logger_config)
        self.logger = self.logger_manager.get_logger()
        self.engine: Optional[Engine] = create_engine(
            self.db_config.get_connection_string(),
            **self._get_engine_args()
        )
        self.uploader: Optional[DifyUploader] = None
        self.schema_engine: Optional[SchemaEngine] = None
        self._initialize_components()

    def _get_engine_args(self) -> dict:
        """SQLAlchemy engine arguments for the configured database type."""
        return sqlalchemy_engine_kwargs(self.db_config.type)

    @staticmethod
    def from_config_file(
        db_config_path: str,
        logger_config_path: str,
        dify_config_path: Optional[str] = None,
    ) -> "LmDbSchemaRagBuilder":
        """
        Factory: build LmDbSchemaRagBuilder from JSON config file paths.
        """
        db_config = read_json(db_config_path)
        logger_config = read_json(logger_config_path)
        dify_config = read_json(dify_config_path) if dify_config_path else None
        # read_json returns dicts; convert to config objects
        db_config_obj = DatabaseConfig(**db_config)
        logger_config_obj = LoggerConfig(**logger_config)
        dify_config_obj = DifyUploadConfig(**dify_config) if dify_config else None
        return LmDbSchemaRagBuilder(db_config_obj, logger_config_obj, dify_config_obj)

    def _initialize_components(self):
        """Initialize schema engine and optional Dify uploader."""
        if not self.engine:
            self.logger.error(
                "[kb_build] phase=engine Database engine was not created; cannot init schema engine"
            )
            raise RuntimeError("Database engine was not created; check database configuration")
        try:
            t0 = time.monotonic()
            self.logger.info(
                "[kb_build] phase=schema_engine_start db_type=%s database=%r include_tables=%s",
                self.db_config.type,
                self.db_config.database,
                self.include_tables,
            )
            self.schema_engine = SchemaEngine(
                engine=self.engine,
                db_name=self.db_config.database,
                include_tables=self.include_tables,
                logger=self.logger,
            )
            self.logger.info(
                "[kb_build] phase=schema_engine_done duration_s=%.2f",
                time.monotonic() - t0,
            )
        except Exception as e:
            self.logger.error(
                "[kb_build] phase=schema_engine_failed db=%r error=%s",
                self.db_config.database,
                e,
                exc_info=True,
            )
            raise RuntimeError(
                f"Cannot initialize schema engine; check database configuration: {e}"
            ) from e
        if self.dify_config:
            try:
                self.uploader = DifyUploader(self.dify_config, self.logger)
                self.logger.info("[kb_build] phase=dify_uploader_ready")
            except ImportError as e:
                self.logger.error(
                    "[kb_build] phase=dify_uploader_failed error=%s", e, exc_info=True
                )
                self.uploader = None

    def generate_dictionary(self) -> Optional[str]:
        """
        Generate the data dictionary text.

        :return: Data dictionary string
        """
        if not self.schema_engine:
            self.logger.error("Schema engine not initialized; cannot generate dictionary")
            raise RuntimeError("Schema engine not initialized; check database connection")
        t0 = time.monotonic()
        self.logger.info("[kb_build] phase=serialize_dictionary_start")
        try:
            mschema = self.schema_engine.mschema
            if not mschema:
                self.logger.error(
                    "[kb_build] phase=serialize_dictionary_failed reason=no_mschema"
                )
                raise RuntimeError("Cannot load database schema; check database connection")
            mschema_str = mschema.to_mschema()
            self.logger.info(
                "[kb_build] phase=serialize_dictionary_done duration_s=%.2f chars=%d tables_in_mschema=%d",
                time.monotonic() - t0,
                len(mschema_str) if mschema_str else 0,
                len(mschema.tables),
            )
            # if save_path:
            #     if save_path.endswith(".json"):
            #         mschema.save(save_path)
            #     elif save_path.endswith(".txt") or save_path.endswith(".md"):
            #         save_raw_text(save_path, mschema_str)
            #     logging.info(f"Data dictionary saved to: {save_path}")
            return mschema_str
        except Exception as e:
            self.logger.error(
                "[kb_build] phase=serialize_dictionary_failed error=%s", e, exc_info=True
            )
            raise

    def upload_file_to_dify(self, file_path: str):
        """
        Upload a file to the Dify knowledge base.

        :param file_path: Path to the file
        """
        if not self.uploader:
            self.logger.error("Dify upload is disabled or failed to initialize")
            raise RuntimeError("Dify upload is disabled or failed to initialize")
        self.logger.info(f"Uploading file to Dify: {file_path}")
        try:
            self.uploader.upload_file(file_path)
        except Exception as e:
            self.logger.error(f"Failed to upload file {file_path} to Dify: {e}")
            raise

    def upload_text_to_dify(self, name: str, content: str):
        """
        Upload text to the Dify knowledge base.

        :param name: Document name
        :param content: Text body
        """
        if not self.uploader:
            self.logger.error("Dify upload is disabled or failed to initialize")
            raise RuntimeError("Dify upload is disabled or failed to initialize")
        t0 = time.monotonic()
        self.logger.info(
            "[kb_build] phase=dify_upload_start name=%r content_chars=%d",
            name,
            len(content) if content else 0,
        )
        try:
            self.uploader.upload_text(name=name, content=content)
            self.logger.info(
                "[kb_build] phase=dify_upload_done name=%r duration_s=%.2f",
                name,
                time.monotonic() - t0,
            )
        except Exception as e:
            self.logger.error(
                "[kb_build] phase=dify_upload_failed name=%r error=%s",
                name,
                e,
                exc_info=True,
            )
            raise

    def run_full_process(self):
        """
        Run full generate-and-upload flow.
        """
        try:
            schema_content = self.generate_dictionary()
            name = f"{self.db_config.database}_schema"
            if self.dify_config and schema_content:
                self.upload_text_to_dify(name=name, content=schema_content)
            self.logger.info("All tasks completed successfully.")
        except Exception as e:
            self.logger.error(f"Pipeline error: {e}")
        finally:
            self.close()

    def close(self):
        """Dispose database connections."""
        if self.engine:
            self.engine.dispose()
            self.logger.info("Database connections closed")
