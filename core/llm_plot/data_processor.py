"""
Transform row dicts into AntV-ready chart data.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_ERR_PREFIX = "Data transformation error"


class DataProcessor:
    """Normalize query result rows for each chart type."""

    @staticmethod
    def transform_data_for_chart(
        chart_type: str,
        data: List[Dict],
        x_field: str,
        y_field: Optional[str] = None
    ) -> List[Any]:
        try:
            if not data:
                raise ValueError("Data list is empty")

            logger.debug(f"Transform start: chart_type={chart_type}, x_field={x_field}, y_field={y_field}")
            logger.debug(f"Row count: {len(data)}, first row: {data[0]}")

            if chart_type == "line":
                return DataProcessor._transform_line_data(data, x_field, y_field)
            if chart_type == "histogram":
                return DataProcessor._transform_histogram_data(data, y_field)
            if chart_type == "pie":
                return DataProcessor._transform_pie_data(data, x_field, y_field)
            raise ValueError(f"Unsupported chart type: {chart_type}")

        except KeyError as e:
            missing_field = str(e).strip("'\"")
            available_fields = list(data[0].keys()) if data else []
            logger.error(
                f"{_ERR_PREFIX}: field '{missing_field}' missing\n"
                f"Available fields: {available_fields}\n"
                f"Sample row: {data[0] if data else 'no data'}"
            )
            raise ValueError(
                f"{_ERR_PREFIX}: field '{missing_field}' missing. "
                f"Available fields: {', '.join(available_fields)}"
            )
        except ValueError as e:
            if _ERR_PREFIX in str(e):
                raise
            logger.error(f"{_ERR_PREFIX}: {str(e)}\nSample row: {data[0] if data else 'no data'}")
            raise ValueError(f"{_ERR_PREFIX}: {str(e)}")

    @staticmethod
    def _transform_line_data(
        data: List[Dict],
        x_field: str,
        y_field: Optional[str]
    ) -> List[Dict[str, Any]]:
        result = []
        if data and y_field:
            if y_field not in data[0]:
                available_fields = list(data[0].keys())
                raise KeyError(
                    f"Field '{y_field}' not found. Available: {', '.join(available_fields)}"
                )
            if x_field not in data[0]:
                available_fields = list(data[0].keys())
                raise KeyError(
                    f"Field '{x_field}' not found. Available: {', '.join(available_fields)}"
                )

        for item in data:
            if y_field:
                y_value = item.get(y_field)
                x_value = item.get(x_field)
                if y_value is not None and x_value is not None:
                    result.append({
                        "time": str(x_value),
                        "value": float(str(y_value).replace(',', ''))
                    })
        return result

    @staticmethod
    def _transform_histogram_data(
        data: List[Dict],
        y_field: Optional[str]
    ) -> List[float]:
        if not y_field:
            return []

        if data and y_field not in data[0]:
            available_fields = list(data[0].keys())
            raise KeyError(
                f"Field '{y_field}' not found. Available: {', '.join(available_fields)}"
            )

        result = []
        for item in data:
            y_value = item.get(y_field)
            if y_value is not None:
                result.append(float(str(y_value).replace(',', '')))
        return result

    @staticmethod
    def _transform_pie_data(
        data: List[Dict],
        x_field: str,
        y_field: Optional[str]
    ) -> List[Dict[str, Any]]:
        result = []

        if data:
            if x_field not in data[0]:
                available_fields = list(data[0].keys())
                raise KeyError(
                    f"Field '{x_field}' not found. Available: {', '.join(available_fields)}"
                )
            if y_field and y_field not in data[0]:
                available_fields = list(data[0].keys())
                raise KeyError(
                    f"Field '{y_field}' not found. Available: {', '.join(available_fields)}"
                )

        if y_field:
            for item in data:
                x_value = item.get(x_field)
                y_value = item.get(y_field)
                if x_value and y_value is not None:
                    category = str(x_value)
                    value = float(str(y_value).replace(',', ''))
                    result.append({
                        "category": category,
                        "value": value
                    })
        else:
            category_count = {}
            for item in data:
                if item.get(x_field):
                    category = str(item[x_field])
                    category_count[category] = category_count.get(category, 0) + 1

            for category, count in category_count.items():
                result.append({
                    "category": category,
                    "value": count
                })

        return result

    @staticmethod
    def clean_data(data: List[Dict]) -> List[Dict]:
        """Drop empty or all-None rows."""
        cleaned = []
        for item in data:
            if item and any(v is not None for v in item.values()):
                cleaned.append(item)
        return cleaned

    @staticmethod
    def get_data_summary(data: List[Dict]) -> Dict[str, Any]:
        """Lightweight stats for debugging."""
        if not data:
            return {
                "record_count": 0,
                "fields": [],
                "sample": None
            }

        return {
            "record_count": len(data),
            "fields": list(data[0].keys()) if data else [],
            "sample": data[0] if data else None
        }
