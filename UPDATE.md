# Dynamic configuration and multi–knowledge-base support

This document describes dynamic configuration and multi–knowledge-base features in SchemaRAG-dify-plugin.

## Version history

### 0.1.7

- **i18n**: English as default in code and logs; `en_US` / `pt_BR` / `zh_Hans` in Dify tool and provider YAMLs.
- **`tools/tool_messages.py`**: centralized chat strings; optional **`ui_language`** on Text to Data, SQL Executor, and Custom SQL Executor (default `en_US`).
- Docs: `docs/TRADUCAO_ATENCAO.md`, `RELEASE_NOTES.md`. See release notes on GitHub for the full list.

### 0.1.6 and earlier

- See git history and previous releases.

## Feature overview

### 1. Multiple knowledge bases

You can retrieve schema text from several Dify datasets at once for broader coverage. Retrieval uses concurrent async calls to Dify to reduce latency.

**How to use**

- Pass comma-separated dataset IDs in `dataset_id`, e.g. `"dataset1,dataset2,dataset3"`.
- The plugin retrieves from each dataset and merges the results.

**Supported tools**

- `text2sql` (and related flows)

**Example**

```
dataset_id: "db_schema_users,db_schema_orders,db_schema_products"
```

### 2. Custom assistant prompts

Optional custom instructions extend the system prompt for SQL generation.

**How to use**

- Set the `custom_prompt` parameter with your rules.
- Content is added under the “Custom Instructions” portion of the system prompt.

**Supported tools**

- `text2sql`

**Example**

```
custom_prompt: "Always use explicit column names, avoid SELECT *, and prefer JOIN over subqueries for better performance."
```

### 3. Dynamic database configuration (tool-level overrides)

Database connection parameters can be overridden at tool level without changing provider credentials.

**How to use**

- Pass connection fields as tool parameters when supported.
- If omitted, values fall back to the provider configuration.
- All override fields are optional; partial overrides are allowed.

**Supported tools**

- `sql_executer` (where applicable)

**Configurable fields (examples)**

- `db_type`: mysql, postgresql, mssql, oracle, dameng, doris, etc.
- `db_host`, `db_port`, `db_user`, `db_password`, `db_name`

### 4. Example knowledge base

An optional `example_dataset_id` points to a dataset of SQL examples. Retrieved examples are merged into the prompt to improve SQL quality. Retrieval is async/concurrent like multi-dataset schema retrieval.

**How to use**

- Set `example_dataset_id` to one or more comma-separated dataset IDs.
- Examples are injected into the Text2SQL prompt template.

**Supported tools**

- `text2sql`

## Backward compatibility

- Single `dataset_id` values behave as before.
- `custom_prompt` and example datasets are optional.
- Tool-level DB overrides are optional; provider defaults apply when not set.

## Use cases

- **Multiple KBs**: teams split schema docs by domain; cross-source questions.
- **Custom prompts**: house SQL style, performance rules, business constraints.
- **Dynamic DB config**: dev/test/prod or ad-hoc analytics connections.

## Best practices

1. **Multiple KBs**: group datasets logically; avoid duplicate chunks; keep docs updated.
2. **Custom prompts**: keep them short and non-contradictory with base instructions.
3. **Dynamic DB**: pass secrets safely; validate connectivity; reuse parameters when possible.
