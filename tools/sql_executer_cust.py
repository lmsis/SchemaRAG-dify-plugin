import sys
import os
from collections.abc import Generator
from typing import Any, Dict, List, Optional
import re
import logging
from urllib.parse import urlparse

from utils import (
    _clean_and_validate_sql,
    PerformanceConfig,
    format_numeric_values,
    create_config_hash,
    LRUCache
)

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)  # Add parent directory to path

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from service.database_service import DatabaseService
from dify_plugin.config.logger_format import plugin_logger_handler
from tools.parameter_validator import validate_and_extract_sql_executer_parameters


class SQLExecuterTool(Tool):
    """
    Custom-connection SQL executor with caching and safety checks.

    Same performance themes as the default executor: LRU service cache,
    numeric formatting, SQL validation, timing logs, config-hash keys.
    """

    _db_service_cache = LRUCache(max_size=PerformanceConfig.CACHE_MAX_SIZE)

    QUERY_TIMEOUT = PerformanceConfig.QUERY_TIMEOUT
    DECIMAL_PLACES = PerformanceConfig.DECIMAL_PLACES

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._db_service = None
        self._db_config = None
        self._config_validated = False
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(plugin_logger_handler)

    @property
    def db_service(self):
        """Lazy DatabaseService with LRU cache keyed by config hash."""
        if self._db_service is None:
            config_key = create_config_hash(self._db_config)

            cached_service = self._db_service_cache.get(config_key)
            if cached_service:
                self._db_service = cached_service
            else:
                new_service = DatabaseService()
                self._db_service_cache.put(config_key, new_service)
                self._db_service = new_service

        return self._db_service

    @classmethod
    def clear_cache(cls):
        """Clear cached DatabaseService instances."""
        cls._db_service_cache.clear()

    @classmethod
    def get_cache_size(cls) -> int:
        """Current LRU cache entry count."""
        return cls._db_service_cache.size()

    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        """
        Execute SQL queries and return results in specified format.
        """
        database_url = tool_parameters.get("database_url")
        if not database_url:
            yield self.create_text_message("Error: database_url is required")
            return

        try:
            parsed = urlparse(database_url)
            self._db_config = {
                "db_type": parsed.scheme,
                "db_host": parsed.hostname,
                "db_port": parsed.port,
                "db_user": parsed.username,
                "db_password": parsed.password,
                "db_name": parsed.path.lstrip('/'),
            }
            self._config_validated = all(
                value is not None for value in self._db_config.values()
            )
            if not self._config_validated:
                yield self.create_text_message("Error: database_url is invalid or incomplete")
                return
        except Exception as e:
            yield self.create_text_message(f"Error: failed to parse database_url: {str(e)}")
            return

        sql_query, output_format, max_rows, error_msg = validate_and_extract_sql_executer_parameters(
            tool_parameters,
            default_max_rows=500,
            logger=self.logger
        )
        if error_msg:
            self.logger.error(f"Error: {error_msg}")
            raise ValueError(error_msg)

        try:
            cleaned_sql = _clean_and_validate_sql(sql_query)
            if not cleaned_sql:
                self.logger.error("Error: invalid SQL query")
                raise ValueError("Invalid SQL query")

            import time

            start_time = time.time()

            self.logger.info(f"Executing SQL: {cleaned_sql[:100]}...")
            results, columns = self.db_service.execute_query(
                self._db_config["db_type"],
                self._db_config["db_host"],
                self._db_config["db_port"],
                self._db_config["db_user"],
                self._db_config["db_password"],
                self._db_config["db_name"],
                cleaned_sql,
            )

            execution_time = time.time() - start_time
            self.logger.info(f"SQL finished in {execution_time:.3f}s")

            result_count = len(results)
            if result_count == 0:
                yield self.create_text_message("Query ran successfully but returned no rows")
                return

            if result_count > max_rows:
                self.logger.warning(
                    f"Warning: {result_count} rows returned, truncated to {max_rows}"
                )
                results = results[:max_rows]

            if results:
                formatted_results = self._format_numeric_values(results)

                formatted_output = self.db_service._format_output(
                    formatted_results, columns, output_format
                )
                yield self.create_text_message(text=formatted_output)

            self.logger.info(f"Result handling complete, {len(results)} row(s) returned")

        except ValueError as e:
            self.logger.error(f"Validation error: {str(e)}")
            raise ValueError(f"Validation error: {str(e)}")

        except ConnectionError as e:
            self.logger.error(f"Database connection error: {str(e)}")
            raise ConnectionError(f"Database connection error: {str(e)}")
        except Exception as e:
            self.logger.error(f"SQL execution error: {str(e)}")
            raise ValueError(f"SQL execution error: {str(e)}")

    def _format_numeric_values(self, results: List[Dict]) -> List[Dict]:
        """Format numbers to avoid scientific notation."""
        return format_numeric_values(results, self.DECIMAL_PLACES, self.logger)
