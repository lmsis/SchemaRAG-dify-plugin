# Multi-dataset and example-KB implementation summary

## Overview

This document summarizes support for **multiple Dify datasets** (comma-separated IDs) and optional **example datasets** that inject few-shot SQL into Text2SQL prompts, as described in [UPDATE.md](../UPDATE.md).

## Implemented capabilities

### 1. Multiple knowledge bases
- **Code:** `service/knowledge_service.py`  
- **Entry point:** `retrieve_schema_from_multiple_datasets()`  
- Comma-separated `dataset_id` values  
- Concurrent async retrieval via **httpx** where possible  
- Fallback sequential path if async fails  
- Merged sections labeled per dataset (see `KnowledgeService` formatting)  

### 2. Example dataset retrieval
- **Code:** `tools/text2sql.py` (and related tools)  
- **Parameter:** `example_dataset_id` (optional)  
- Retrieves example segments and passes them into the prompt builder  

### 3. Parameter validation
- **Code:** `tools/parameter_validator.py` (`validate_and_extract_text2sql_parameters`, etc.)  
- Validates dialects, retrieval modes, `example_dataset_id` type, memory and cache flags  

### 4. Prompt updates
- **Code:** `prompt/text2sql_prompt.py`  
- User prompt includes `【Database Schema】`, optional `【Examples】`, and conversation history when enabled  

### 5. Tool YAML
- **`tools/text2sql.yaml`:** documents `example_dataset_id` and multi-dataset `dataset_id`  

## Technical notes

- Async concurrency reduces wall-clock time vs strict serial retrieval.  
- Backward compatible: a single `dataset_id` still works.  
- New fields are optional.  

## Files commonly involved

1. `service/knowledge_service.py`  
2. `tools/text2sql.py`  
3. `tools/text2sql.yaml`  
4. `prompt/text2sql_prompt.py`  
5. `tools/parameter_validator.py`  

## Tests

- `test/test_multiple_dataset_support.py`  

## Follow-ups (ideas)

- Metrics for concurrent retrieval  
- Tunable timeouts/retries  
- Stronger caching of merged schema payloads  
- End-user docs aligned with current Dify UI  

**Status:** Feature set described above is implemented; verify against your branch and Dify version.
