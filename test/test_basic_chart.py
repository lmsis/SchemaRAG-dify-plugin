"""
Basic chart generation smoke tests.
"""

import sys
import os
from pathlib import Path

# Project root on path
sys.path.append(str(Path(__file__).parent.parent))

from core.llm_plot.chart_generator import ChartGenerator

def test_basic_bar_chart():
    """Generate a simple bar chart (PNG)."""
    print("\n🧪 Basic bar chart")

    output_dir = Path("output/basic_test")
    output_dir.mkdir(parents=True, exist_ok=True)

    chart_gen = ChartGenerator(str(output_dir))

    config = {
        "chart_type": "bar",
        "title": "Test bar chart",
        "x_axis": {
            "label": "Category",
            "data": ["A", "B", "C", "D", "E"]
        },
        "y_axis": {
            "label": "Value",
            "data": [10, 15, 7, 12, 9]
        },
        "style": {
            "format": "png",
            "colors": ["#3498db"]
        },
        "description": "Smoke test bar chart"
    }

    try:
        chart_path = chart_gen.generate_chart(config)
        print(f"✅ Bar chart: {chart_path}")
        return True
    except Exception as e:
        print(f"❌ Bar chart failed: {str(e)}")
        return False

def test_basic_pie_chart():
    """Generate a simple pie chart (PNG)."""
    print("\n🧪 Basic pie chart")

    output_dir = Path("output/basic_test")
    output_dir.mkdir(parents=True, exist_ok=True)

    chart_gen = ChartGenerator(str(output_dir))

    config = {
        "chart_type": "pie",
        "title": "Test pie chart",
        "pie_data": {
            "labels": ["A", "B", "C", "D"],
            "values": [35, 25, 20, 15]
        },
        "style": {
            "format": "png",
            "high_contrast": True
        },
        "description": "Smoke test pie chart"
    }

    try:
        chart_path = chart_gen.generate_chart(config)
        print(f"✅ Pie chart: {chart_path}")
        return True
    except Exception as e:
        print(f"❌ Pie chart failed: {str(e)}")
        return False

def test_svg_output():
    """Generate a line chart as SVG."""
    print("\n🧪 SVG line chart")

    output_dir = Path("output/basic_test")
    output_dir.mkdir(parents=True, exist_ok=True)

    chart_gen = ChartGenerator(str(output_dir))

    config = {
        "chart_type": "line",
        "title": "Test line chart (SVG)",
        "x_axis": {
            "label": "Time",
            "data": ["Jan", "Feb", "Mar", "Apr", "May"]
        },
        "line_series": [
            {
                "label": "Series A",
                "data": [10, 15, 13, 17, 20]
            }
        ],
        "style": {
            "format": "svg",
            "grid": True,
            "grid_alpha": 0.6
        },
        "description": "Smoke test line chart (SVG)"
    }

    try:
        chart_path = chart_gen.generate_chart(config)
        print(f"✅ SVG line chart: {chart_path}")
        return True
    except Exception as e:
        print(f"❌ SVG line chart failed: {str(e)}")
        return False

def run_tests():
    """Run all chart smoke tests."""
    print("=" * 50)
    print("📊 Chart generator smoke tests")
    print("=" * 50)

    tests = [
        test_basic_bar_chart,
        test_basic_pie_chart,
        test_svg_output
    ]

    results = []
    for test in tests:
        results.append(test())

    print("\n" + "=" * 50)
    success_count = results.count(True)
    total_count = len(results)
    print(f"📋 Results: {success_count}/{total_count} passed")

    if success_count == total_count:
        print("✅ All passed")
    else:
        print("❌ Some failed")

    print(f"📁 Output: {os.path.abspath('output/basic_test')}")

if __name__ == "__main__":
    run_tests()
