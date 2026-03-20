from collections.abc import Generator
from typing import Any, Optional, List, Dict
import sys
import os
import re
import logging
from prompt import text2sql_prompt, summary_prompt
from service.knowledge_service import KnowledgeService
from service.database_service import DatabaseService
from service.sql_refiner import SQLRefiner
from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from dify_plugin.entities.model.message import SystemPromptMessage, UserPromptMessage
from dify_plugin.config.logger_format import plugin_logger_handler

from utils import (
    _clean_and_validate_sql,
    PerformanceConfig,
    format_numeric_values
)

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


class Text2DataTool(Tool):
    """
    Text to Data — turn natural language into SQL, execute, return formatted data.

    Features:
    1. Multi-dataset retrieval for schema
    2. Optional example dataset for better SQL quality
    3. SQL safety validation (dangerous statements blocked)
    4. Max row limit
    5. Numeric formatting without scientific notation
    """

    DEFAULT_TOP_K = 5
    DEFAULT_DIALECT = "mysql"
    DEFAULT_RETRIEVAL_MODEL = "semantic_search"
    DEFAULT_MAX_ROWS = 500
    MAX_CONTENT_LENGTH = 10000
    DECIMAL_PLACES = PerformanceConfig.DECIMAL_PLACES

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.api_uri = self.runtime.credentials.get("api_uri")
        self.dataset_api_key = self.runtime.credentials.get("dataset_api_key")
        self.knowledge_service = KnowledgeService(self.api_uri, self.dataset_api_key)
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(plugin_logger_handler)

        self.db_service = DatabaseService()

        credentials = self.runtime.credentials
        self.db_type = credentials.get("db_type")
        self.db_host = credentials.get("db_host")
        self.db_port = (
            int(credentials.get("db_port")) if credentials.get("db_port") else None
        )
        self.db_user = credentials.get("db_user")
        self.db_password = credentials.get("db_password")
        self.db_name = credentials.get("db_name")

    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        """
        Convert natural language to SQL, execute, and return formatted results.
        """
        try:
            dataset_id = tool_parameters.get("dataset_id")
            llm_model = tool_parameters.get("llm")
            content = tool_parameters.get("content")
            dialect = tool_parameters.get("dialect", self.DEFAULT_DIALECT)
            top_k = tool_parameters.get("top_k", self.DEFAULT_TOP_K)
            retrieval_model = tool_parameters.get("retrieval_model", self.DEFAULT_RETRIEVAL_MODEL)
            output_format = tool_parameters.get("output_format", "json")
            max_rows = tool_parameters.get("max_rows", self.DEFAULT_MAX_ROWS)
            example_dataset_id = tool_parameters.get("example_dataset_id")

            enable_refiner = tool_parameters.get("enable_refiner", "False")
            if isinstance(enable_refiner, str):
                enable_refiner = enable_refiner.lower() in ['true', '1', 'yes']
            elif not isinstance(enable_refiner, bool):
                enable_refiner = False

            max_refine_iterations = tool_parameters.get("max_refine_iterations", 3)

            if not dataset_id:
                self.logger.error("Error: dataset_id is required")
                raise ValueError("dataset_id is required")

            if not content:
                self.logger.error("Error: question content is required")
                raise ValueError("Question content is required")

            if len(content) > self.MAX_CONTENT_LENGTH:
                self.logger.error(f"Error: question too long, max length is {self.MAX_CONTENT_LENGTH}")
                raise ValueError(f"Question too long, max length is {self.MAX_CONTENT_LENGTH}")

            if not llm_model:
                self.logger.error("Error: LLM model configuration is required")
                raise ValueError("LLM model configuration is required")

            if not self.api_uri or not self.dataset_api_key:
                self.logger.error("Error: API configuration is incomplete")
                raise ValueError("Invalid API configuration")

            if not all([self.db_type, self.db_host, self.db_port, self.db_user, self.db_password, self.db_name]):
                self.logger.error("Error: database configuration is incomplete")
                raise ValueError("Invalid database configuration")

            if not isinstance(max_rows, int) or max_rows < 1:
                self.logger.warning(f"Invalid max_rows={max_rows}, using default {self.DEFAULT_MAX_ROWS}")
                max_rows = self.DEFAULT_MAX_ROWS

            self.logger.info(f"Retrieving schema from dataset(s) {dataset_id}, query length: {len(content)}")

            try:
                schema_info = self.knowledge_service.retrieve_schema_from_multiple_datasets(
                    dataset_id, content, top_k, retrieval_model
                )
            except Exception as e:
                self.logger.error(f"Error retrieving schema: {str(e)}")
                schema_info = "No relevant database schema was found"

            if not schema_info or not schema_info.strip():
                self.logger.warning("No relevant schema retrieved from knowledge base")
                schema_info = "No relevant database schema was found"

            example_info = ""
            if example_dataset_id and example_dataset_id.strip():
                self.logger.info(f"Retrieving examples from dataset(s) {example_dataset_id}")
                try:
                    example_info = self.knowledge_service.retrieve_schema_from_multiple_datasets(
                        example_dataset_id, content, top_k, retrieval_model
                    )
                    if example_info and example_info.strip():
                        self.logger.info(f"Retrieved examples, length: {len(example_info)}")
                    else:
                        self.logger.info("No relevant examples retrieved")
                except Exception as e:
                    self.logger.warning(f"Error retrieving examples: {str(e)}")
                    example_info = ""

            self.logger.info("Generating SQL query...")

            yield self.create_text_message(text="<think>\n💭 Generating SQL query\n\n")

            try:
                system_prompt = text2sql_prompt._build_system_prompt(dialect=dialect)
                user_prompt = text2sql_prompt._build_user_prompt(
                    db_schema=schema_info,
                    question=content,
                    example_info=example_info
                )

                response = self.session.model.llm.invoke(
                    model_config=llm_model,
                    prompt_messages=[
                        SystemPromptMessage(content=system_prompt),
                        UserPromptMessage(content=user_prompt),
                    ],
                    stream=True,
                )

                sql_query = ""
                sql_chunks = []

                yield self.create_text_message(text="\n")

                for chunk in response:
                    if chunk.delta.message and chunk.delta.message.content:
                        chunk_content = chunk.delta.message.content
                        sql_chunks.append(chunk_content)
                        yield self.create_text_message(text=chunk_content)

                sql_query = "".join(sql_chunks).strip()

                if not sql_query and hasattr(response, "message") and response.message:
                    sql_query = response.message.content.strip() if response.message.content else ""

                if not sql_query:
                    self.logger.error("Error: failed to generate SQL")
                    raise ValueError("Generated SQL is empty")

                sql_query = _clean_and_validate_sql(sql_query)

                if not sql_query or not sql_query.strip():
                    self.logger.error("Error: generated SQL is empty or invalid")
                    raise ValueError("Generated SQL is empty or invalid")

                yield self.create_text_message(text="\n\n")

            except Exception as e:
                self.logger.error(f"Error while generating SQL: {str(e)}")
                yield self.create_text_message(text="</think>\n")
                raise

            self.logger.info("Executing SQL query...")

            try:
                results, columns = self.db_service.execute_query(
                    self.db_type, self.db_host, self.db_port,
                    self.db_user, self.db_password, self.db_name, sql_query
                )
                yield self.create_text_message(text=f"✅ Execution succeeded\n\nReturned {len(results)} row(s)\n\n")

            except Exception as e:
                self.logger.error(f"SQL execution error: {str(e)}")
                yield self.create_text_message(text=f"❌ Execution failed\n\n{str(e)}\n\n")

                if enable_refiner:
                    self.logger.info("SQL execution failed, starting SQL Refiner...")
                    yield self.create_text_message(text="\n🔧 Auto-fix in progress...\n")

                    try:
                        refiner = SQLRefiner(
                            db_service=self.db_service,
                            llm_session=self.session,
                            logger=self.logger
                        )

                        db_config = {
                            'db_type': self.db_type,
                            'host': self.db_host,
                            'port': self.db_port,
                            'user': self.db_user,
                            'password': self.db_password,
                            'dbname': self.db_name
                        }

                        refined_sql, success, error_history = refiner.refine_sql(
                            original_sql=sql_query,
                            schema_info=schema_info,
                            question=content,
                            dialect=dialect,
                            db_config=db_config,
                            llm_model=llm_model,
                            max_iterations=max_refine_iterations
                        )

                        if success:
                            self.logger.info(f"SQL refinement succeeded after {len(error_history)} iteration(s)")
                            yield self.create_text_message(
                                text=f"✨ Refined successfully ({len(error_history)} attempt(s))\n\n{refined_sql}\n\n"
                            )

                            results, columns = self.db_service.execute_query(
                                self.db_type, self.db_host, self.db_port,
                                self.db_user, self.db_password, self.db_name, refined_sql
                            )

                            sql_query = refined_sql
                            yield self.create_text_message(text=f"✅ Execution succeeded\n\nReturned {len(results)} row(s)\n\n")

                        else:
                            error_report = refiner.format_refiner_result(
                                original_sql=sql_query,
                                refined_sql=refined_sql,
                                success=False,
                                error_history=error_history,
                                iterations=len(error_history)
                            )
                            self.logger.error(f"SQL refinement failed: {error_report}")
                            yield self.create_text_message(text="</think>\n")
                            raise ValueError(f"SQL execution failed and auto-fix failed:\n\n{error_report}")

                    except Exception as refiner_error:
                        self.logger.error(f"SQL Refiner error: {str(refiner_error)}")
                        yield self.create_text_message(text="</think>\n")
                        raise ValueError(f"SQL execution failed: {str(e)}\n\nRefiner also failed: {str(refiner_error)}")
                else:
                    yield self.create_text_message(text="</think>\n")
                    raise

            yield self.create_text_message(text="</think>\n\n")

            result_count = len(results)
            if result_count == 0:
                yield self.create_text_message("📊 **Query result**\n\nQuery ran successfully but returned no rows")
                return

            if result_count > max_rows:
                self.logger.warning(f"Warning: query returned {result_count} rows, truncated to {max_rows}")
                results = results[:max_rows]

            formatted_results = self._format_numeric_values(results)

            if output_format == "summary":
                yield from self._handle_summary_output(formatted_results, columns, content, llm_model)
            else:
                try:
                    formatted_output = self.db_service._format_output(formatted_results, columns, output_format)
                    yield self.create_text_message(text=formatted_output)
                except Exception as e:
                    self.logger.error(f"Output formatting error: {str(e)}")
                    raise ValueError(f"Output formatting error: {str(e)}")

            self.logger.info(f"Query handling complete, returning {len(results)} row(s)")

        except Exception as e:
            self.logger.error(f"Execution error: {str(e)}")
            raise ValueError(f"Execution error: {str(e)}")

    def _handle_summary_output(self, formatted_results: List[Dict], columns: List[str],
                               content: str, llm_model: Any) -> Generator[ToolInvokeMessage]:
        """Summary output mode: LLM summarizes tabular results."""
        self.logger.info("Generating data summary...")

        try:
            json_data = self.db_service._format_output(formatted_results, columns, "json")

            if not json_data or json_data.strip() == "":
                self.logger.warning("Warning: empty result set, cannot generate summary")
                return

            summary_system_prompt = summary_prompt._data_summary_prompt(json_data, content)

            summary_response = self.session.model.llm.invoke(
                model_config=llm_model,
                prompt_messages=[
                    SystemPromptMessage(content=summary_system_prompt),
                    UserPromptMessage(content="Please produce a concise summary of the data above."),
                ],
                stream=True,
            )

            summary_result = ""
            for chunk in summary_response:
                if chunk.delta.message and chunk.delta.message.content:
                    summary_content = chunk.delta.message.content
                    summary_result += summary_content
                    yield self.create_text_message(text=summary_content)

            if not summary_result and hasattr(summary_response, "message") and summary_response.message:
                summary_result = summary_response.message.content
                if summary_result:
                    yield self.create_text_message(text=summary_result)

        except Exception as e:
            self.logger.error(f"Summary generation error: {str(e)}")
            try:
                formatted_output = self.db_service._format_output(formatted_results, columns, "json")
                self.logger.warning("Summary failed, returning raw JSON data")
                yield self.create_text_message(text=formatted_output)
            except Exception as e2:
                self.logger.error(f"Data formatting also failed: {str(e2)}")
                raise

    def _format_numeric_values(self, results: List[Dict]) -> List[Dict]:
        """Format numbers to avoid scientific notation."""
        return format_numeric_values(results, self.DECIMAL_PLACES, self.logger)
