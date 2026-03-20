# Text2SQL context memory

## Overview

Text2SQL can keep a short **conversation history** (question + generated SQL per turn) keyed by Dify user id, so follow-up questions can be answered with prior context.

## Features

### Multi-turn memory
- Stores each turn’s query and SQL (plus metadata)  
- Configurable **window size** (see `parameter_validator` / tool YAML for current max)  
- **Per-user isolation** via `user_id`  

### Context in prompts
- When memory is on, recent turns are formatted and injected into the **user** prompt (see `prompt/text2sql_prompt.py` and `ContextFormatter`)  
- Helps for refinements (“only active users”, “order by …”, etc.)  

### Controls
- Toggle with `memory_enabled`  
- `reset_memory` clears history for the current user before the run  
- Stale contexts can be expired in storage (see `ContextManager` / storage implementation)  

## Parameters (typical)

### `memory_enabled`
- Type: boolean / string (`true`/`false`)  
- Default: off  
- When on, prior turns are loaded (unless reset).  

### `memory_window_size`
- Type: number  
- Default: `3`  
- How many recent turns to include (bounded by validation in `parameter_validator`).  

### `reset_memory`
- When true, clears stored history for that user before this invocation.  

## Example dialogues

**Refinement**
```
User: List all users
SQL:  SELECT * FROM users

User: Only active users
SQL:  SELECT * FROM users WHERE status = 'active'

User: Sort by signup date
SQL:  SELECT * FROM users WHERE status = 'active' ORDER BY created_at DESC
```

**Analytics drill-down** — same pattern: narrow filters, add `GROUP BY`, then `LIMIT`.  

## Best practices

- Enable when users iterate on the **same** analytical thread.  
- Disable for unrelated one-off questions.  
- Prefer smaller windows to save tokens unless you need long threads.  
- Call **reset** when switching topic, database, or after bad SQL polluted history.  

## Architecture

```
service/context/
├── models.py           # Conversation, UserContext
├── storage.py          # MemoryContextStorage (in-process)
└── context_manager.py  # ContextManager API

prompt/components/
└── context_formatter.py
```

**Flow**
1. User sends question  
2. If memory on and not reset → load history  
3. `ContextFormatter` builds a history block  
4. `_build_user_prompt(..., conversation_history=...)` includes schema + examples + history  
5. After successful generation → `add_conversation(...)`  

## Performance / safety

- In-memory store: shared manager; eviction/TTL behavior is implementation-defined — see code  
- History trimmed to window size to limit tokens  
- Concurrency: storage uses locking where needed  

## Code snippets

```python
from service.context import ContextManager

cm = ContextManager()
cm.add_conversation(
    query="List all users",
    sql="SELECT * FROM users",
    user_id="user_123",
    metadata={"dialect": "mysql"},
)
history = cm.get_conversation_history(user_id="user_123", window_size=3)
cm.reset_memory(user_id="user_123")
```

Inside a tool (pattern):

```python
conversation_history = []
if memory_enabled and not reset_memory:
    conversation_history = self._context_manager.get_conversation_history(
        user_id=user_id,
        window_size=memory_window_size,
    )

user_prompt = text2sql_prompt._build_user_prompt(
    db_schema=schema_info,
    question=content,
    example_info=example_info,
    conversation_history=conversation_history,
)

if memory_enabled and generated_sql:
    self._context_manager.add_conversation(
        query=content,
        sql=generated_sql,
        user_id=user_id,
        metadata={"dialect": dialect, "dataset_id": dataset_id},
    )
```

## Troubleshooting

| Symptom | Things to check |
|--------|------------------|
| SQL “remembers” wrong thread | `reset_memory=true`; shrink window; verify prior SQL quality |
| History never appears | `memory_enabled`; same `user_id`; `reset_memory` not always true |
| Memory growth | Many distinct user IDs; tighten TTL/window in code if you fork |

## Tests

```bash
python test/test_context_manager.py
```

## Future ideas

- Redis / DB-backed storage  
- Summarize long histories  
- Semantic retrieval of relevant past turns  

## Summary

Memory makes multi-step NL→SQL workflows feel natural. Tune **window** and **reset** to balance context vs. tokens and stability.
