# SQL Refiner — implementation notes

## Date
2024-01-26 (original); keep in sync with code when updating this doc.

## Goal
Add an **experimental** SQL auto-repair path to **Text2Data**: when execution fails, optionally run an LLM-guided repair loop before giving up.

## New / central modules

### `service/sql_refiner.py`
- **`SQLRefiner`** — main repair orchestration  
- **`refine_sql()`** — iterative repair  
- **`_validate_sql()`** — lightweight execute / `LIMIT 0` style checks (see code)  
- **`_generate_refined_sql()`** — calls the LLM with refiner prompts  
- **`_clean_sql()`** — strips markdown fences, whitespace  
- **`format_refiner_result()`** — human-readable success/failure report  

### `prompt/sql_refiner_prompt.py`
- System/user prompt builders for the refiner pass  
- Helpers to format validation errors for the model  

### `test/test_sql_refiner.py`
- Unit tests for cleaning, validation hooks, formatting  
- Integration-style tests with mocks  

### `docs/SQL_REFINER_GUIDE.md`
- Operator-facing guide (parameters, FAQ, security)  

## Modified integration points

### `tools/text2data.py`
- Imports and constructs `SQLRefiner` when enabled  
- Reads `enable_refiner` and `max_refine_iterations`  
- On execution failure, enters refiner loop, then retries execution  
- Surfaces repair outcome to the user (see implementation for exact messages)  

### `tools/text2data.yaml`
- Declares `enable_refiner` and `max_refine_iterations` for the Dify UI  

## Architecture (conceptual)

```
User question
    → generate SQL (text2data)
    → execute (DatabaseService)
    → on failure + enable_refiner:
          SQLRefiner.refine_sql()
              validate → LLM fix → validate → … (≤ max_refine_iterations)
    → re-run execute with last candidate SQL
    → return data or error report
```

**Dependencies:** `SQLRefiner` uses `DatabaseService` for validation, LLM session for generation, and `sql_refiner_prompt` for templates.

## Design highlights

1. **Closed loop** — each iteration sees the latest error and history.  
2. **Rich context** — schema, question, failing SQL, and errors go to the LLM.  
3. **Guardrails** — max iterations; repaired SQL re-validated; SELECT-oriented workflows only.  
4. **Operational cost** — extra LLM calls and latency; monitor success rate.  

## Performance (rough expectations)

- Validation via `LIMIT 0` (or equivalent) avoids full scans.  
- Typical repair: 1–3 iterations; a few seconds per iteration depending on model and schema size.  
- Token use roughly a few thousand per iteration when schema is large.  

## Security

- Reuse existing SQL safety rules (SELECT-only tools, etc.).  
- Do not log secrets; refiner logs should redact connection details.  

## Testing

- `uv run pytest test/test_sql_refiner.py` (when the environment resolves dependencies)  

## Related documents
- [SQL Refiner guide](./SQL_REFINER_GUIDE.md)  
- [Text2Data / README](../README.md)  
- [Database support](./DATABASE_SUPPORT_UPDATE.md)  

## Disclaimer
Treat Refiner as **experimental** until you validate it on your schemas, models, and SLOs.
