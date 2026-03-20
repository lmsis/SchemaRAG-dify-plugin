"""
Validate tool parameters for LLM Plot.
"""

import json
from typing import Any, Dict


class ParameterValidator:
    """Input validation for chart tools."""

    @staticmethod
    def validate_parameters(parameters: Dict[str, Any]) -> None:
        """
        Validate required keys and non-empty values.

        Raises:
            ValueError: On missing or empty required parameters
        """
        required_params = ['user_question', 'sql_query', 'data', 'llm']
        for param in required_params:
            if param not in parameters:
                raise ValueError(f"Missing required parameter: {param}")
            if not parameters[param]:
                raise ValueError(f"Parameter cannot be empty: {param}")

        ParameterValidator.validate_data_format(parameters['data'])

    @staticmethod
    def validate_data_format(data: Any) -> None:
        """Ensure `data` is valid JSON when provided as a string."""
        try:
            if isinstance(data, str):
                json.loads(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Parameter 'data' must be valid JSON: {str(e)}")

    @staticmethod
    def validate_chart_type(chart_type: str) -> None:
        """Restrict chart_type to supported values."""
        valid_types = ['line', 'histogram', 'pie']
        if chart_type not in valid_types:
            raise ValueError(
                f"Invalid chart type: {chart_type}. "
                f"Allowed: {', '.join(valid_types)}"
            )

    @staticmethod
    def validate_field_exists(data: list, field_name: str) -> None:
        """Check that field_name exists on the first row."""
        if not data:
            raise ValueError("Data cannot be empty")

        if field_name and field_name not in data[0]:
            available_fields = list(data[0].keys())
            raise ValueError(
                f"Field '{field_name}' is not present in the data. "
                f"Available fields: {', '.join(available_fields)}"
            )
