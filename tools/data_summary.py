from collections.abc import Generator
from typing import Any, Optional
import sys
import os
import json
import logging
from prompt.summary_prompt import _data_summary_prompt
from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from dify_plugin.entities.model.message import SystemPromptMessage, UserPromptMessage
from dify_plugin.config.logger_format import plugin_logger_handler
# Ensure project root is on sys.path for service imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


class DataSummaryTool(Tool):
    """
    Data Summary Tool - Analyze and summarize data content using LLM with optional custom rules
    """

    MAX_DATA_LENGTH = 50000  # max data payload size
    MAX_RULES_LENGTH = 2000  # max custom rules length

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(plugin_logger_handler)

    def _validate_input_data(
        self, data_content: str, query: str, custom_rules: Optional[str] = None
    ) -> tuple[bool, str]:
        """Validate payload size and required fields."""
        if not data_content or not data_content.strip():
            return False, "Data content cannot be empty"

        if not query or not query.strip():
            return False, "Analysis query cannot be empty"

        if len(data_content) > self.MAX_DATA_LENGTH:
            return False, f"Data content too long; max {self.MAX_DATA_LENGTH} characters"

        if custom_rules and len(custom_rules) > self.MAX_RULES_LENGTH:
            return False, f"Custom rules too long; max {self.MAX_RULES_LENGTH} characters"

        return True, ""

    def _format_data_content(self, data_content: str, data_format: str = "auto") -> str:
        """Pretty-print JSON when input looks like JSON."""
        # Detect JSON by leading brace/bracket
        if data_format == "json" or (
            data_format == "auto" and data_content.lstrip().startswith(("{", "["))
        ):
            try:
                parsed_data = json.loads(data_content)
                return json.dumps(parsed_data, indent=2, ensure_ascii=False)
            except json.JSONDecodeError:
                pass

        return data_content.strip()

    def _truncate_data_if_needed(
        self, data_content: str, max_length: int = None
    ) -> tuple[str, bool]:
        """Truncate to max_length when needed; return (text, truncated_flag)."""
        if max_length is None:
            max_length = self.MAX_DATA_LENGTH

        if len(data_content) <= max_length:
            return data_content, False

        truncated_data = data_content[: max_length - 100]  # reserve space for notice
        truncated_data += "\n\n[Note: content was truncated; showing a partial sample]"

        return truncated_data, True

    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        """Stream an LLM summary over the provided data (optional custom prompt/rules)."""
        try:
            # Parameters
            data_content = tool_parameters.get("data_content", "")
            query = tool_parameters.get("query", "")
            llm_model = tool_parameters.get("llm")
            custom_rules = tool_parameters.get("custom_rules", "")
            user_prompt = tool_parameters.get(
                "user_prompt", ""
            )
            data_format = "auto"

            if not llm_model:
                self.logger.error("Missing LLM model configuration")
                raise ValueError("LLM model configuration is required")

            is_valid, error_message = self._validate_input_data(
                data_content, query, custom_rules
            )
            if not is_valid:
                self.logger.error(f"Input validation failed: {error_message}")
                raise ValueError(error_message)

            try:
                formatted_data = self._format_data_content(data_content, data_format)
                self.logger.info("Data formatting complete")
            except Exception as e:
                self.logger.warning(f"Data formatting failed; using raw text: {str(e)}")
                formatted_data = data_content

            final_data, was_truncated = self._truncate_data_if_needed(formatted_data)
            if was_truncated:
                self.logger.info("Data was truncated before analysis")

            if user_prompt and user_prompt.strip():
                system_prompt_content = (
                    "You are a professional data analyst. Follow the user's custom "
                    "instructions and analyze the provided data."
                )
                user_prompt_content = user_prompt.replace(
                    "{{data}}", final_data
                ).replace("{{query}}", query)
                self.logger.info("Using user-defined prompt template")
            elif custom_rules and custom_rules.strip():
                analysis_prompt = _data_summary_prompt(final_data, query, custom_rules)
                system_prompt_content = (
                    "You are a professional data analyst. Apply the given rules and "
                    "analyze the data in depth."
                )
                user_prompt_content = analysis_prompt
                self.logger.info("Using custom rules in the analysis prompt")
            else:
                analysis_prompt = _data_summary_prompt(final_data, query)
                system_prompt_content = (
                    "You are a professional data analyst. Analyze the data to answer the question."
                )
                user_prompt_content = analysis_prompt
                self.logger.info("Using default analysis prompt")

            self.logger.info("Invoking LLM for data analysis...")

            try:
                response = self.session.model.llm.invoke(
                    model_config=llm_model,
                    prompt_messages=[
                        SystemPromptMessage(content=system_prompt_content),
                        UserPromptMessage(content=user_prompt_content),
                    ],
                    stream=True,
                )
                has_streamed_content = False
                total_content_length = 0

                for chunk in response:
                    if chunk.delta.message and chunk.delta.message.content:
                        content = chunk.delta.message.content
                        has_streamed_content = True
                        total_content_length += len(content)
                        # if total_content_length > 50000:
                        #     yield self.create_text_message("Warning: response truncated")
                        #     break
                        yield self.create_text_message(text=content)

                if (
                    not has_streamed_content
                    and hasattr(response, "message")
                    and response.message
                ):
                    yield self.create_text_message(text=response.message.content)

                self.logger.info(f"Analysis complete, response length: {total_content_length}")

            except Exception as e:
                error_msg = f"LLM invocation error: {str(e)}"
                self.logger.error(error_msg)
                raise ValueError(error_msg)

        except Exception as e:
            error_msg = f"Data summary tool failed: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            raise ValueError(error_msg)
