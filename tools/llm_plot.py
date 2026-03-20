"""
LLM Plot tool — chart recommendation and rendering (modular stack).
"""

from collections.abc import Generator
import json
import logging
from typing import Any

from pydantic import ValidationError

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from core.llm_plot import (
    ParameterValidator,
    LLMAnalyzer,
    ChartGenerator,
)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class LlmPlotTool(Tool):
    """Dify tool: NL + SQL + rows -> chart image URL."""

    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        """
        Args:
            tool_parameters: Tool inputs from Dify

        Yields:
            Tool messages (markdown image link)
        """
        try:
            ParameterValidator.validate_parameters(tool_parameters)

            user_question = tool_parameters['user_question']
            sql_query = tool_parameters['sql_query']
            data = json.loads(
                tool_parameters['data']
                if isinstance(tool_parameters['data'], str)
                else tool_parameters['data']
            )
            llm_model = tool_parameters['llm']

            logger.debug(f"Parameters: {json.dumps(tool_parameters, ensure_ascii=False)}")

            data_fields = list(data[0].keys()) if data and len(data) > 0 else []
            logger.debug(f"Data fields: {data_fields}")

            analyzer = LLMAnalyzer(self.session)
            recommendation = analyzer.analyze(user_question, sql_query, llm_model, data_fields)

            logger.debug(
                f"LLM recommendation: type={recommendation.chart_type}, "
                f"x={recommendation.x_field}, y={recommendation.y_field}, "
                f"title={recommendation.title}"
            )

            generator = ChartGenerator()
            chart_url = generator.generate(recommendation, data)

            result_message = f"""![Generated chart]({chart_url})"""
            yield self.create_text_message(result_message)

        except ValueError as e:
            error_msg = f"Parameter error: {str(e)}"
            logger.error("ValueError | %s | %s", str(e), type(e).__name__)
            yield self.create_text_message(error_msg)

        except json.JSONDecodeError as e:
            error_msg = "Invalid data: please provide valid JSON"
            logger.error(
                "JSON decode error | %s | %s | doc=%s",
                str(e),
                type(e).__name__,
                e.doc[:200] if hasattr(e, 'doc') else 'N/A'
            )
            yield self.create_text_message(error_msg)

        except ValidationError as e:
            error_msg = f"Validation error: {str(e)}"
            logger.error("ValidationError | %s | %s", str(e), type(e).__name__)
            yield self.create_text_message(error_msg)

        except Exception as e:
            error_msg = f"Chart generation failed: {str(e)}"
            logger.error(
                "Unexpected error | %s | %s | traceback=%s",
                str(e),
                type(e).__name__,
                getattr(e, '__traceback__', 'N/A'),
                exc_info=True
            )
            yield self.create_text_message(error_msg)
