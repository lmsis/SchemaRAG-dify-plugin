"""
Chinese font rendering for charts.

Verifies CJK labels render correctly in generated chart files.
"""

import sys
import os
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Project root on path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.llm_plot import generate_chart

def test_chinese_fonts():
    """Generate sample charts with CJK text (font smoke test)."""
    logger.info("Starting Chinese font smoke test...")

    output_dir = Path("output/charts")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Bar chart with CJK labels
    logger.info("Generating bar chart with CJK labels...")
    bar_config = {
        "chart_type": "bar",
        "title": "各地区销售业绩对比",
        "x_axis": {
            "label": "地区",
            "data": ["北京", "上海", "广州", "深圳", "杭州"]
        },
        "y_axis": {
            "label": "销售额（万元）",
            "data": [120, 150, 100, 130, 110]
        },
        "style": {
            "figure_size": [10, 6],
            "dpi": 100
        }
    }

    try:
        chart_path = generate_chart(bar_config, str(output_dir))
        logger.info(f"Bar chart OK: {chart_path}")
        print(f"✅ Bar chart (CJK): {chart_path}")
    except Exception as e:
        logger.error(f"Bar chart failed: {str(e)}")
        print(f"❌ Bar chart (CJK) failed: {str(e)}")

    # Pie chart with CJK labels
    logger.info("Generating pie chart with CJK labels...")
    pie_config = {
        "chart_type": "pie",
        "title": "市场份额分布情况",
        "pie_data": {
            "labels": ["华为", "小米", "苹果", "三星", "其他品牌"],
            "values": [30, 25, 20, 15, 10]
        },
        "style": {
            "figure_size": [8, 8],
            "dpi": 100
        }
    }

    try:
        chart_path = generate_chart(pie_config, str(output_dir))
        logger.info(f"Pie chart OK: {chart_path}")
        print(f"✅ Pie chart (CJK): {chart_path}")
    except Exception as e:
        logger.error(f"Pie chart failed: {str(e)}")
        print(f"❌ Pie chart (CJK) failed: {str(e)}")

    # Line chart with CJK labels
    logger.info("Generating line chart with CJK labels...")
    line_config = {
        "chart_type": "line",
        "title": "各季度产品销量趋势",
        "x_axis": {
            "label": "季度",
            "data": ["第一季度", "第二季度", "第三季度", "第四季度"]
        },
        "line_series": [
            {
                "label": "高端产品",
                "data": [150, 180, 210, 230]
            },
            {
                "label": "中端产品",
                "data": [250, 220, 280, 300]
            },
            {
                "label": "入门产品",
                "data": [350, 380, 330, 390]
            }
        ],
        "style": {
            "figure_size": [10, 6],
            "dpi": 100
        }
    }

    try:
        chart_path = generate_chart(line_config, str(output_dir))
        logger.info(f"Line chart OK: {chart_path}")
        print(f"✅ Line chart (CJK): {chart_path}")
    except Exception as e:
        logger.error(f"Line chart failed: {str(e)}")
        print(f"❌ Line chart (CJK) failed: {str(e)}")

    print("\nSummary:")
    print("- If charts were created and CJK glyphs look correct, font setup is OK.")
    print("- Output directory:", output_dir.absolute())
    print("- Open the files to confirm CJK rendering.")

if __name__ == "__main__":
    test_chinese_fonts()
