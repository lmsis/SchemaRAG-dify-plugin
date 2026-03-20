"""
LLM-based chart recommendation.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from dify_plugin.entities.model.message import SystemPromptMessage, UserPromptMessage

from .models import ChartRecommendation

logger = logging.getLogger(__name__)


class LLMAnalyzer:
    """Calls the LLM to pick chart type and fields."""

    SYSTEM_PROMPT = """You are a data visualization expert. Analyze the user's question and SQL, then recommend the best chart.

Reply with a single valid JSON string (no markdown fences) containing:
{
    "chart_type": "one of: line, histogram, pie",
    "x_field": "X-axis or category column name",
    "y_field": "Y-axis or numeric column (optional for pie)",
    "title": "chart title",
    "description": "brief rationale for this chart type"
}

Chart selection:
1. line — time series and trends
2. histogram — numeric distributions
3. pie — parts of a whole / structure

Critical rules:
- x_field and y_field MUST come from the provided "available data fields" list when that list is given
- Names must match exactly (including non-ASCII characters and case)
- Do not invent generic English names (e.g. category, value, sales) unless they are real column names in the data
- Return raw JSON only; do not wrap in ```json``` fences"""

    DEFAULT_RECOMMENDATION = {
        "chart_type": "pie",
        "x_field": "category",
        "y_field": "value",
        "title": "Data distribution",
        "description": "Pie chart to show share of each segment."
    }

    def __init__(self, session):
        self.session = session

    def analyze(
        self,
        user_question: str,
        sql_query: str,
        llm_model: Dict[str, Any],
        data_fields: Optional[List[str]] = None
    ) -> ChartRecommendation:
        """Run the model and parse a ChartRecommendation; fall back to defaults on error."""
        try:
            user_prompt = self._build_user_prompt(user_question, sql_query, data_fields)
            response_text = self._invoke_llm(llm_model, user_prompt)
            return self._parse_response(response_text, data_fields)

        except Exception as e:
            logger.error(f"LLM analysis failed: {str(e)}")
            return self._get_default_recommendation(data_fields)

    def _build_user_prompt(self, user_question: str, sql_query: str, data_fields: list = None) -> str:
        fields_info = ""
        if data_fields:
            fields_info = f"\nAvailable data fields: {', '.join(data_fields)}"

        return f"""Analyze the following question and SQL, and recommend a visualization.

User question: {user_question}
SQL query: {sql_query}{fields_info}

Important: x_field and y_field must be chosen from the available fields list above when it is provided.
Use column names that actually appear in the SQL/result. Answer with JSON only."""

    def _invoke_llm(self, llm_model: Dict[str, Any], user_prompt: str) -> str:
        response_generator = self.session.model.llm.invoke(
            model_config=llm_model,
            prompt_messages=[
                SystemPromptMessage(content=self.SYSTEM_PROMPT),
                UserPromptMessage(content=user_prompt),
            ],
            stream=False
        )

        response_text = ""
        for key, value in response_generator:
            if key == 'message' and hasattr(value, 'content'):
                response_text = value.content
                break

        logger.debug(f"LLM full response: {response_text}")
        return response_text

    def _extract_json_from_response(self, response_text: str) -> str:
        """Strip markdown fences or isolate a JSON object from free text."""
        if not response_text:
            return response_text

        text = response_text.strip()

        code_block_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        match = re.search(code_block_pattern, text)
        if match:
            return match.group(1).strip()

        json_pattern = r'\{[\s\S]*\}'
        match = re.search(json_pattern, text)
        if match:
            return match.group(0)

        return text

    def _parse_response(
        self,
        response_text: str,
        data_fields: Optional[List[str]] = None
    ) -> ChartRecommendation:
        try:
            json_text = self._extract_json_from_response(response_text)
            recommendation = json.loads(json_text)
            return ChartRecommendation(**recommendation)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"Failed to parse LLM response: {str(e)}\nResponse: {response_text}")
            return self._get_default_recommendation(data_fields)

    def _get_default_recommendation(
        self,
        data_fields: Optional[List[str]] = None
    ) -> ChartRecommendation:
        if data_fields and len(data_fields) >= 2:
            return ChartRecommendation(
                chart_type="line",
                x_field=data_fields[0],
                y_field=data_fields[1],
                title="Trend analysis",
                description="Line chart for trend over the first two columns."
            )
        if data_fields and len(data_fields) == 1:
            return ChartRecommendation(
                chart_type="pie",
                x_field=data_fields[0],
                y_field=None,
                title="Data distribution",
                description="Pie chart for the single available category column."
            )
        return ChartRecommendation(**self.DEFAULT_RECOMMENDATION)

    @classmethod
    def create_recommendation(
        cls,
        chart_type: str,
        x_field: str,
        y_field: str = None,
        title: str = "",
        description: str = ""
    ) -> ChartRecommendation:
        return ChartRecommendation(
            chart_type=chart_type,
            x_field=x_field,
            y_field=y_field,
            title=title or f"{chart_type.capitalize()} Chart",
            description=description or f"Visualization using {chart_type} chart"
        )
