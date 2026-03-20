"""
Pydantic models for chart recommendations.
"""

from typing import Optional
from pydantic import BaseModel, Field


class ChartRecommendation(BaseModel):
    """Structured chart recommendation from the LLM."""
    chart_type: str = Field(..., description="Chart type: line, histogram, or pie")
    x_field: str = Field(..., description="X-axis or category field name")
    y_field: Optional[str] = Field(None, description="Y-axis or numeric field (optional for pie)")
    title: str = Field(..., description="Chart title")
    description: str = Field(..., description="Why this chart type fits the data")

    class Config:
        json_schema_extra = {
            "example": {
                "chart_type": "line",
                "x_field": "date",
                "y_field": "sales",
                "title": "Sales trend",
                "description": "Shows how sales change over time"
            }
        }
