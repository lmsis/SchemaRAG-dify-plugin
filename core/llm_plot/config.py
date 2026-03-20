"""
Chart templates for AntV GPT-Vis.

AntV GPT-Vis accepts only:
- type (required)
- data (required)
- title, axisXTitle, axisYTitle (optional)
- theme: "default" | "dark" | "academy"
- style: backgroundColor, palette, lineWidth
- binNumber (histogram only)

Extra keys (width, legend, etc.) yield 400 errors.

See: https://github.com/antvis/GPT-Vis
"""

from typing import Dict, Any, List


class ChartConfig:
    """Defaults and merge helpers for AntV payloads."""

    ANTV_API_URL = "https://antv-studio.alipay.com/api/gpt-vis"

    BASE_CONFIG: Dict[str, Any] = {
        "theme": "academy",
        "style": {
            "backgroundColor": "#ffffff",
            "palette": [
                "#5B8FF9",
                "#61DDAA",
                "#F6BD16",
                "#7262fd",
                "#78D3F8",
                "#9661BC",
                "#F6903D",
                "#008685",
                "#F08BB4",
            ]
        }
    }

    LINE_CHART_TEMPLATE: Dict[str, Any] = {
        "type": "line",
        "title": "Line chart",
        "axisXTitle": "X",
        "axisYTitle": "Y",
        "style": {
            "lineWidth": 3
        }
    }

    HISTOGRAM_CHART_TEMPLATE: Dict[str, Any] = {
        "type": "histogram",
        "title": "Histogram",
        "binNumber": 10,
        "axisXTitle": "Value range",
        "axisYTitle": "Frequency"
    }

    PIE_CHART_TEMPLATE: Dict[str, Any] = {
        "type": "pie",
        "title": "Pie chart"
    }

    @classmethod
    def get_chart_template(cls, chart_type: str) -> Dict[str, Any]:
        templates = {
            "line": cls.LINE_CHART_TEMPLATE,
            "histogram": cls.HISTOGRAM_CHART_TEMPLATE,
            "pie": cls.PIE_CHART_TEMPLATE,
        }
        return templates.get(chart_type, cls.PIE_CHART_TEMPLATE).copy()

    @classmethod
    def merge_config(cls, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = cls.merge_config(result[key], value)
            else:
                result[key] = value
        return result

    @classmethod
    def create_chart_config(
        cls,
        chart_type: str,
        data: List[Any],
        title: str = "",
        x_title: str = "",
        y_title: str = "",
        **kwargs
    ) -> Dict[str, Any]:
        config = cls.merge_config(cls.BASE_CONFIG, cls.get_chart_template(chart_type))

        config["data"] = data
        if title:
            config["title"] = title
        if x_title and "axisXTitle" in config:
            config["axisXTitle"] = x_title
        if y_title and "axisYTitle" in config:
            config["axisYTitle"] = y_title

        if kwargs:
            config = cls.merge_config(config, kwargs)

        return config
