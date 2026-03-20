"""
Build chart configs and call AntV GPT-Vis API.
"""

import json
import logging
from typing import Any, Dict, List

import requests

from .config import ChartConfig
from .data_processor import DataProcessor
from .models import ChartRecommendation

logger = logging.getLogger(__name__)


class ChartGenerator:
    """End-to-end: rows -> config -> chart URL."""

    def __init__(self):
        self.config = ChartConfig()
        self.data_processor = DataProcessor()

    def generate_chart_config(
        self,
        recommendation: ChartRecommendation,
        data: List[Dict]
    ) -> Dict[str, Any]:
        chart_data = self.data_processor.transform_data_for_chart(
            recommendation.chart_type,
            data,
            recommendation.x_field,
            recommendation.y_field
        )

        if recommendation.chart_type == "line":
            return self._generate_line_config(recommendation, chart_data)
        if recommendation.chart_type == "histogram":
            return self._generate_histogram_config(recommendation, chart_data, data)
        if recommendation.chart_type == "pie":
            return self._generate_pie_config(recommendation, chart_data)
        raise ValueError(f"Unsupported chart type: {recommendation.chart_type}")

    def _generate_line_config(
        self,
        recommendation: ChartRecommendation,
        chart_data: List[Dict]
    ) -> Dict[str, Any]:
        return self.config.create_chart_config(
            chart_type="line",
            data=chart_data,
            title=recommendation.title,
            x_title=recommendation.x_field,
            y_title=recommendation.y_field or ""
        )

    def _generate_histogram_config(
        self,
        recommendation: ChartRecommendation,
        chart_data: List[float],
        original_data: List[Dict]
    ) -> Dict[str, Any]:
        bin_number = min(10, len(original_data) // 5) or 5

        return self.config.create_chart_config(
            chart_type="histogram",
            data=chart_data,
            title=recommendation.title,
            x_title=f"{recommendation.y_field or recommendation.x_field} bins",
            y_title="Count",
            binNumber=bin_number
        )

    def _generate_pie_config(
        self,
        recommendation: ChartRecommendation,
        chart_data: List[Dict]
    ) -> Dict[str, Any]:
        return self.config.create_chart_config(
            chart_type="pie",
            data=chart_data,
            title=recommendation.title
        )

    def generate_chart_url(self, config: Dict[str, Any]) -> str:
        try:
            logger.debug(f"POST chart config to AntV: {json.dumps(config, ensure_ascii=False)}")

            response = requests.post(
                ChartConfig.ANTV_API_URL,
                json=config,
                headers={
                    'Content-Type': 'application/json',
                    'Accept': '*/*',
                    'User-Agent': 'Dify-Plugin-Visualization/1.0'
                },
                timeout=30
            )
            response.raise_for_status()
            response_data = response.json()

            logger.debug(f"AntV response: {json.dumps(response_data, ensure_ascii=False)}")

            if 'success' in response_data and not response_data['success']:
                error_msg = response_data.get('errorMessage', 'Unknown error')
                raise ValueError(f"AntV API error: {error_msg}")

            if 'resultObj' in response_data and isinstance(response_data['resultObj'], str):
                return response_data['resultObj']

            raise ValueError("No valid chart URL in AntV API response")

        except requests.exceptions.Timeout:
            logger.error("AntV API request timed out")
            raise ValueError("AntV API request timed out; try again later")
        except requests.exceptions.RequestException as e:
            logger.error(f"AntV API request failed: {str(e)}")
            raise ValueError(f"AntV API request failed: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid AntV JSON: {str(e)}\nBody: {response.text}")
            raise ValueError(f"Failed to parse AntV response: {str(e)}")
        except Exception as e:
            logger.error(f"Chart generation error: {str(e)}")
            raise ValueError(f"Chart generation error: {str(e)}")

    def generate(
        self,
        recommendation: ChartRecommendation,
        data: List[Dict]
    ) -> str:
        config = self.generate_chart_config(recommendation, data)
        return self.generate_chart_url(config)
