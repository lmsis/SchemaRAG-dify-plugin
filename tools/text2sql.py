from collections.abc import Generator
from typing import Any, Dict
import sys
import os
import logging
from prompt import text2sql_prompt
from service.knowledge_service import KnowledgeService
from service.context import ContextManager
from service.cache import CacheManager, normalize_query, create_cache_key_from_dict, CacheConfig
from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from dify_plugin.entities.model.message import SystemPromptMessage, UserPromptMessage
from tools.parameter_validator import validate_and_extract_text2sql_parameters

from dify_plugin.config.logger_format import plugin_logger_handler

# Add project root to Python path for service imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


class Text2SQLTool(Tool):
    # Class-level knowledge service cache
    _knowledge_service_cache = {}
    # Cache size cap to avoid unbounded growth
    _cache_max_size = 10

    # Defaults and limits
    DEFAULT_TOP_K = 5
    DEFAULT_DIALECT = "mysql"
    DEFAULT_RETRIEVAL_MODEL = "semantic_search"
    MAX_CONTENT_LENGTH = 10000
    DEFAULT_MEMORY_WINDOW = 3

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_uri = self.runtime.credentials.get("api_uri")
        self.dataset_api_key = self.runtime.credentials.get("dataset_api_key")
        self._knowledge_service = None
        self._config_validated = False
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(plugin_logger_handler)

        self._context_manager = ContextManager()
        self._sql_cache = CacheManager.get_instance("sql_cache")

        self._validate_config()

    @property
    def knowledge_service(self):
        """Lazily create KnowledgeService; reuse cached instance per API config."""
        if self._knowledge_service is None:
            cache_key = f"{self.api_uri}:{self.dataset_api_key}"

            if cache_key not in self._knowledge_service_cache:
                if len(self._knowledge_service_cache) >= self._cache_max_size:
                    oldest_key = next(iter(self._knowledge_service_cache))
                    del self._knowledge_service_cache[oldest_key]

                self._knowledge_service_cache[cache_key] = KnowledgeService(
                    self.api_uri, self.dataset_api_key
                )

            self._knowledge_service = self._knowledge_service_cache[cache_key]

        return self._knowledge_service

    def _validate_config(self):
        """Validate API credentials are present."""
        self._config_validated = bool(self.api_uri and self.dataset_api_key)
        if not self._config_validated:
            self.logger.warning("API configuration is incomplete")

    @classmethod
    def clear_cache(cls):
        """Clear the knowledge service instance cache."""
        cls._knowledge_service_cache.clear()

    @classmethod
    def get_cache_size(cls) -> int:
        """Return number of cached knowledge service instances."""
        return len(cls._knowledge_service_cache)

    @classmethod
    def get_cache_stats(cls) -> Dict[str, Any]:
        """
        Return aggregate cache statistics.

        Returns:
            Dict summarizing cache configuration/state.
        """
        return CacheConfig.get_summary()

    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        """
        Convert natural language questions to SQL queries using database schema knowledge base
        """
        if not self._config_validated:
            logging.error("Error: missing API configuration")
            raise ValueError("Invalid API configuration")

        try:
            params_result = validate_and_extract_text2sql_parameters(
                tool_parameters,
                max_content_length=self.MAX_CONTENT_LENGTH,
                default_top_k=self.DEFAULT_TOP_K,
                default_dialect=self.DEFAULT_DIALECT,
                default_retrieval_model=self.DEFAULT_RETRIEVAL_MODEL,
                default_memory_window=self.DEFAULT_MEMORY_WINDOW
            )
            if isinstance(params_result, str):
                logging.error(f"Error: {params_result}")
                raise ValueError(params_result)

            (dataset_id, llm_model, content, dialect, top_k, retrieval_model,
             custom_prompt, example_dataset_id, memory_enabled, memory_window_size, reset_memory, cache_enabled) = params_result

            user_id = self.runtime.user_id

            if reset_memory:
                self.logger.info(f"Resetting conversation memory for user_id={user_id}")
                self._context_manager.reset_memory(user_id)

            self.logger.info(
                f"Retrieving schema from dataset(s) {dataset_id}, query length: {len(content)}"
            )

            schema_info = self.knowledge_service.retrieve_schema_from_multiple_datasets(
                dataset_id, content, top_k, retrieval_model
            )

            if not schema_info or not schema_info.strip():
                self.logger.warning("No relevant schema retrieved from knowledge base")
                schema_info = "No relevant database schema was found"

            example_info = ""
            if example_dataset_id and example_dataset_id.strip():
                self.logger.info(f"Retrieving examples from dataset(s) {example_dataset_id}")
                example_info = self.knowledge_service.retrieve_schema_from_multiple_datasets(
                    example_dataset_id, content, top_k, retrieval_model
                )
                if example_info and example_info.strip():
                    self.logger.info(f"Retrieved examples, length: {len(example_info)}")
                else:
                    self.logger.info("No relevant examples retrieved")

            conversation_history = []
            if memory_enabled and not reset_memory:
                conversation_history = self._context_manager.get_conversation_history(
                    user_id=user_id,
                    window_size=memory_window_size
                )
                if conversation_history:
                    self.logger.info(f"Loaded {len(conversation_history)} prior conversation turn(s)")

            system_prompt = text2sql_prompt._build_system_prompt(
                dialect, custom_prompt
            )
            user_prompt = text2sql_prompt._build_user_prompt(
                db_schema=schema_info,
                question=content,
                example_info=example_info,
                conversation_history=conversation_history
            )

            cache_key = None
            if cache_enabled and not reset_memory:
                cache_key = create_cache_key_from_dict(
                    "sql",
                    {
                        "dialect": dialect,
                        "query": normalize_query(content),
                        "dataset_id": dataset_id,
                        "custom_prompt": custom_prompt[:50] if custom_prompt else ""
                    }
                )

                cached_sql = self._sql_cache.get(cache_key)
                if cached_sql:
                    self.logger.info("SQL cache hit, returning cached SQL")
                    yield self.create_text_message(text=cached_sql)

                    if memory_enabled:
                        self._context_manager.add_conversation(
                            query=content,
                            sql=cached_sql,
                            user_id=user_id,
                            metadata={
                                "dialect": dialect,
                                "dataset_id": dataset_id,
                                "from_cache": True
                            }
                        )
                        self.logger.debug(f"Saved cached SQL to context for user: {user_id}")

                    return

            self.logger.info("SQL cache miss, invoking LLM to generate SQL")

            response = self.session.model.llm.invoke(
                model_config=llm_model,
                prompt_messages=[
                    SystemPromptMessage(content=system_prompt),
                    UserPromptMessage(
                        content=user_prompt
                    ),
                ],
                stream=True,
            )

            has_streamed_content = False
            total_content_length = 0
            generated_sql = ""

            for chunk in response:
                if chunk.delta.message and chunk.delta.message.content:
                    sql_content = chunk.delta.message.content
                    has_streamed_content = True
                    total_content_length += len(sql_content)
                    generated_sql += sql_content

                    if total_content_length > 50000:
                        logging.warning("Warning: response too long, truncated")
                        break

                    yield self.create_text_message(text=sql_content)

            if (
                not has_streamed_content
                and hasattr(response, "message")
                and response.message
            ):
                generated_sql = response.message.content
                yield self.create_text_message(text=generated_sql)

            self.logger.info(f"SQL generation finished, response length: {total_content_length}")

            if cache_enabled and generated_sql and cache_key:
                self._sql_cache.set(cache_key, generated_sql, ttl=7200)
                self.logger.debug(f"Stored generated SQL in cache, key: {cache_key}")

            if memory_enabled and generated_sql:
                self._context_manager.add_conversation(
                    query=content,
                    sql=generated_sql,
                    user_id=user_id,
                    metadata={
                        "dialect": dialect,
                        "dataset_id": dataset_id
                    }
                )
                self.logger.debug(f"Saved conversation to context for user: {user_id}")

        except ValueError as e:
            self.logger.error(f"Parameter validation error: {str(e)}")
            raise ValueError(f"Invalid parameters: {str(e)}")
        except ConnectionError as e:
            self.logger.error(f"Network error: {str(e)}")
            raise ValueError(f"Network error: {str(e)}")
        except Exception as e:
            self.logger.error(f"SQL generation error: {str(e)}")
            raise ValueError(f"SQL generation error: {str(e)}")
