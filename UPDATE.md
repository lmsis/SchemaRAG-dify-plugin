# Dynamic configuration and multi–knowledge-base support

This document describes dynamic configuration and multi–knowledge-base features in **LM DB Schema RAG** (`lm-db-schema-rag`).

## Version history

### 1.0.4

- **Tool `schema_kb_build`:** parâmetro **`dataset_id`** alinhado ao **Text to SQL** (`string`, `form: llm`); removido `dynamic-select` / `_fetch_parameter_options`. Vários IDs separados por vírgula → usa-se só o **primeiro** no upload.

### 1.0.3

- **Validação ao guardar credenciais:** apenas **`SELECT 1`** na BD + pedido mínimo à API Dify (`list_datasets`); **não** extrai schema nem faz upload.
- **Removida** a credencial `kb_build_in_background` (e o build em thread no provider).
- **Nova tool `schema_kb_build`:** build completo (extração + upload) **síncrono** no workflow; saída **`true`** / **`false`**. (Parâmetro de destino refinado na **1.0.4**.)

### 1.0.2

- **Credencial `kb_build_in_background`:** se ativa, validação faz só **`SELECT 1`** na BD; extração de schema + upload Dify correm numa **thread em background** (daemon) e o guardar credenciais devolve logo OK. Erros do build aparecem nos logs do plugin-daemon (`[provider] phase=background_kb_thread_*`). *(Removido na 1.0.3 — usar a tool `schema_kb_build`.)*
- **`ping_database_connection` / `sqlalchemy_engine_kwargs`** em `service/schema_builder.py` para o ping rápido e kwargs partilhados do engine.

### 1.0.1

- **KB build observability:** logs por fase (`[sql_database]`, `[schema_engine]`, `[kb_build]`, `[provider]`) com tempos, ETA durante `mschema`, **objeto x/y** por tabela e progresso de colunas em tabelas largas.
- **Plugin timeout:** `DIFY_PLUGIN_MAX_REQUEST_TIMEOUT` (default **14400** s) em `main.py` para builds de schema grandes.
- **SchemaEngine:** logger opcional injetado pelo builder; avisos em falhas de `DISTINCT` por coluna.

### 1.0.0

First **stable release line** for **LM DB Schema RAG** (`lmsis/lm_db_schema_rag`) after packaging, CI, and self-hosted install paths were validated:

- Plugin id **`lmsis/lm_db_schema_rag`**; author **`lmsis`**; i18n (`en_US` / `pt_BR` / `zh_Hans`), optional **`ui_language`** on selected tools.
- **GitHub Release** ships **`lm_db_schema_rag-1.0.0.difypkg`** via `release-attach-difypkg.yml`; optional **signing** with repo secret **`PLUGIN_SIGNING_PRIVATE_PEM`** (see `docs/PLUGIN_SIGNING.md`).
- Workflows that opened PRs to `langgenius/dify-plugins` are **disabled**; distribution is **this repo + `.difypkg`**, not the official marketplace monorepo.
- Tool YAML fixes for `dify-plugin package` (quoted strings where colons broke parsing).

Earlier experimental tags (`v0.2.x`, etc.) were **removed** from release history on purpose; details remain in **git log** if needed.

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
