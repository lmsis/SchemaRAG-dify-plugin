# LLM Plot core package

Modular components behind the **LLM Plot** tool: validation, LLM-driven chart recommendation, data shaping, and AntV-based rendering.

## Layout

```
core/llm_plot/
├── __init__.py
├── README.md
├── models.py
├── config.py
├── validator.py
├── data_processor.py
├── llm_analyzer.py
└── chart_generator.py
```

## Modules

### `models.py`
- `ChartRecommendation` — chart type, fields, titles, etc.

### `config.py`
- `ChartConfig.BASE_CONFIG`, line / histogram / pie templates  
- `get_chart_template()`, `create_chart_config()`  

**Template notes**
- **Line** — trends/time series; configurable line width, legend-friendly defaults  
- **Histogram** — distribution; bin count heuristics  
- **Pie** — shares/structure; donut-friendly defaults (`innerRadius` where supported by downstream API)  

### `validator.py`
- `validate_parameters`, `validate_data_format`, `validate_chart_type`, `validate_field_exists`, etc.

### `data_processor.py`
- `transform_data_for_chart`, `clean_data`, `get_data_summary`  

**Shapes (typical)**
- Line: `[{"time": "...", "value": ...}, ...]`  
- Histogram: `[v1, v2, ...]`  
- Pie: `[{"category": "...", "value": ...}, ...]`  

### `llm_analyzer.py`
- `analyze()` — user question + SQL context → recommendation  
- `create_recommendation()` — default / structured output  

### `chart_generator.py`
- `generate_chart_config`, `generate_chart_url`, full `generate()` pipeline  

## Usage sketch

```python
from core.llm_plot import (
    ParameterValidator,
    LLMAnalyzer,
    ChartGenerator,
)

ParameterValidator.validate_parameters(parameters)
analyzer = LLMAnalyzer(session)
recommendation = analyzer.analyze(user_question, sql_query, llm_model)
generator = ChartGenerator()
chart_url = generator.generate(recommendation, data)
```

### Custom config

```python
from core.llm_plot import ChartConfig

config = ChartConfig.create_chart_config(
    chart_type="line",
    data=chart_data,
    title="Sales trend",
    x_title="Date",
    y_title="Revenue",
    style={"lineWidth": 5},
)
```

### Data processing

```python
from core.llm_plot import DataProcessor

processor = DataProcessor()
chart_data = processor.transform_data_for_chart(
    chart_type="pie",
    data=raw_data,
    x_field="category",
    y_field="value",
)
summary = processor.get_data_summary(data)
print(summary["record_count"], summary["fields"])
```

## Design goals

1. Small, testable modules  
2. Easy to add chart types  
3. Reusable outside this plugin if needed  
4. Sane defaults for AntV / GPT-Vis payloads  
5. Pydantic models where applicable  
6. Clear errors + logging  

## Palette (reference)

```python
palette = [
    "#5B8FF9",  # blue
    "#61DDAA",  # green
    "#F6BD16",  # yellow
    "#7262fd",  # purple
    "#78D3F8",  # cyan
    "#9661BC",  # deep purple
    "#F6903D",  # orange
    "#008685",  # teal
    "#F08BB4",  # pink
]
```

## AntV GPT-Vis API

- **URL:** `https://antv-studio.alipay.com/api/gpt-vis`  
- **Timeout:** ~30s (see code)  
- **Theme:** e.g. `academy`  

### Allowed payload (summary)

| Field | Notes |
|-------|--------|
| `type` | `line` / `pie` / `histogram`, etc. |
| `data` | array (required) |
| `title`, `axisXTitle`, `axisYTitle` | optional |
| `theme` | `default` \| `dark` \| `academy` |
| `style` | limited keys: e.g. `backgroundColor`, `palette`, `lineWidth` |
| `binNumber` | histogram only |

Extra keys (`width`, `height`, rich `legend` objects, …) may cause **400** responses — keep payloads minimal.

Reference: [GPT-Vis](https://github.com/antvis/GPT-Vis)

## Version / deps

- Intended for **Python 3.12+** in this repo (see root `pyproject.toml`)  
- Uses `pydantic`, HTTP client stack, `dify_plugin`  

## Contributing

1. Keep modules focused  
2. Document non-obvious behavior  
3. Add tests under `test/`  
4. Match existing style  
5. Update this README when behavior changes  
