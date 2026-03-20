
# SQL Refiner Guide

## Overview

SQL Refiner is an **experimental** module that automatically detects and repairs SQL execution errors using an LLM feedback loop.

## Features

### Capabilities
1. **Error detection** — captures execution failures
2. **Root-cause hints** — uses error text and schema context
3. **Iterative repair** — multiple attempts with refined SQL
4. **Context-aware** — keeps schema and user question in the prompt
5. **Error history** — prior failures are passed to the model to avoid repeats

### Typical error classes
- Wrong or misspelled column names
- Missing or wrong table names
- Dialect-specific syntax issues
- Type mismatches in predicates
- Bad JOIN conditions
- Misused aggregates

## Quick start

### Parameters (Text2Data)
- `enable_refiner`: `true` to turn Refiner on
- `max_refine_iterations`: max repair attempts (e.g. `3`)

### Example payload
```python
{
    "dataset_id": "your_dataset_id",
    "llm": "your_llm_model",
    "content": "Count orders per user",
    "dialect": "mysql",
    "enable_refiner": true,
    "max_refine_iterations": 3
}
```

## How it works

1. User question → initial SQL generated  
2. Execute SQL → on failure, if Refiner is enabled  
3. Refiner loop: capture error → build repair prompt → LLM proposes SQL → validate → repeat up to N times  
4. Return repaired SQL or a structured failure report  

## Example: wrong column name

- **Question:** list each user’s name and email  
- **Bad SQL:** `SELECT name, email FROM users`  
- **Error:** `Unknown column 'name' in 'field list'`  
- **Fixed:** `SELECT username, email FROM users`  
- **Outcome:** often succeeds within 1–2 iterations  

## Configuration

### `enable_refiner`
- Type: boolean  
- Default: `false`  
- Enables automatic SQL repair  

### `max_refine_iterations`
- Type: number  
- Range: 1–5  
- Default: `3`  

## Best practices

### When to enable
- Good: complex schemas, multi-table joins, vague questions  
- Avoid: trivial single-table queries, strict latency SLOs, unreviewed production without testing  

### Tips
- Keep schema documentation rich (types, comments, relationships)  
- Store common query patterns in an example dataset  
- Start with 3 iterations unless you have a reason to change it  

## Monitoring / logs

Example log lines:
```
[INFO] SQL execution failed; starting SQL Refiner...
[INFO] SQL repair iteration 1/3
[WARNING] Attempt 1 failed: Unknown column 'name'
[INFO] SQL repair succeeded after 2 iteration(s)
```

## FAQ

**Q: Extra latency?**  
A: Roughly 2–3 seconds per iteration; total often 5–10 seconds.

**Q: Token cost?**  
A: On the order of 1.7k–3k tokens per iteration, depending on schema size.

**Q: What if repair fails?**  
A: You get an error report; verify schema coverage and consider manual fixes.

## Security

- Repaired SQL still goes through existing safety checks  
- Intended for **SELECT** workflows  
- Database permissions remain enforced  

## Related docs
- [Text2Data / README](../README.md)  
- [Database support](./DATABASE_SUPPORT_UPDATE.md)  
- [Testing](./TESTING_GUIDE.md)  
