# Text2SQL cache optimization

## Overview

The project includes a **generic in-memory cache** (LRU + TTL) to speed up Text2SQL and related paths. Goals:

- **Simple and fast** — process-local memory backends  
- **Extensible** — decorators + `CacheManager` pattern  
- **Maintainable** — shared config and stats APIs  
- **Observable** — hit/miss counters and summaries  

## Layout

```
service/cache/
├── __init__.py
├── base.py
├── memory.py
├── decorators.py
├── config.py
└── utils.py
```

### Layers

```
┌─────────────────────────────────────────┐
│         Tools (e.g. Text2SQL)           │
├─────────────────────────────────────────┤
│   @cacheable decorators / CacheManager   │
├─────────────────────────────────────────┤
│   LRU / TTL in-memory implementations   │
└─────────────────────────────────────────┘
```

## What is cached today

### 1. Schema retrieval
- **Where:** `service/knowledge_service.py`  
- **What:** dataset retrieval results  
- **Key material:** `dataset_id`, normalized query, `top_k`, `retrieval_model` (see decorator / key generator in code)  
- **TTL:** on the order of **1 hour** (see `CacheConfig`)  
- **Condition:** usually non-empty results only  

### 2. Generated SQL
- **Where:** `tools/text2sql.py`  
- **What:** final streamed SQL string  
- **Key material:** dialect, normalized question, `dataset_id`, prefix of `custom_prompt`  
- **TTL:** on the order of **2 hours**  
- **Note:** skipped when `reset_memory` clears contextual need for reuse (see tool logic)  

### 3. Query normalization
- **Where:** `service/cache/utils.py` — `normalize_query()`  
- **Why:** improves hit rate by canonicalizing whitespace / case / stopwords (see implementation)  

## Default configuration (illustrative)

```python
{
    "schema_cache": {"type": "lru", "max_size": 100, "ttl": 3600},
    "sql_cache": {"type": "lru", "max_size": 50, "ttl": 7200},
    "prompt_cache": {"type": "lru", "max_size": 20, "ttl": 86400},
}
```

Tune via `CacheConfig.update_cache_config(...)`.

## Usage patterns

### Decorator (typical)

```python
from service.cache import cacheable

@cacheable(
    name="my_cache",
    key_prefix="prefix",
    ttl=3600,
    condition=lambda result: result is not None,
)
def expensive_fn(a, b):
    ...
```

### Manual cache

```python
from service.cache import CacheManager, create_cache_key_from_dict

cache = CacheManager.get_instance("my_cache")
key = create_cache_key_from_dict("prefix", {"a": 1, "b": 2})
hit = cache.get(key)
if hit is not None:
    return hit
out = expensive_operation()
cache.set(key, out, ttl=3600)
return out
```

## Statistics

```python
from service.cache import CacheConfig, CacheManager

summary = CacheConfig.get_summary()
stats = CacheManager.get_instance("schema_cache").get_stats()
```

## Expected impact

| Area | Without cache | With cache hit |
|------|---------------|----------------|
| Schema HTTP call | ~200–500 ms | sub-ms local read |
| SQL LLM call | ~1–3 s | sub-ms local read |

Overall, similar questions can cut end-to-end latency and provider cost materially.

## Improving hit rate

1. Rely on `normalize_query()`  
2. Increase TTL where schema changes are rare  
3. Warm common queries once after deploy  
4. Watch stats and adjust `max_size` / TTL  

## Adding cache to another tool

```python
from service.cache import cacheable, CacheManager

class MyTool:
    def __init__(self):
        self._cache = CacheManager.get_instance("my_tool_cache")

    @cacheable(name="my_tool_cache", key_prefix="my_tool", ttl=1800)
    def step(self, x, y):
        ...
```

Steps: register config (optional), pick decorator vs manual API, add tests, monitor.

## Best practices

**Do**
- Cache expensive I/O and LLM calls  
- Normalize inputs used in keys  
- Set TTL aligned with data freshness  
- Inspect hit rate periodically  
- Cache only successful / meaningful results (`condition=`)  

**Don’t**
- Cache highly volatile or secret payloads  
- Use unbounded caches in long-lived workers  
- Ignore invalidation when upstream docs change  
- Store passwords or PII in values  

## Troubleshooting

### Cache never hits
- Manager not initialized / wrong key fields  
- TTL too short  
- Query normalization mismatch  

### High RAM
- Lower `max_size`  
- Shorten TTL  
- Shrink stored payload size  

### Low hit rate
- Overly specific keys  
- TTL too aggressive  
- Users issue unique phrasing — tune normalization  

## Extensions

- Redis / Memcached backend implementing `CacheBackend`  
- Distributed invalidation hooks  
- Optional ML-based admission policy  

## Summary

Caching is a first-class tool for Text2SQL latency and cost. Pair **normalization**, **TTL**, and **monitoring** to keep results fresh without wasting memory.
