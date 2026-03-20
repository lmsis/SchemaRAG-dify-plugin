# Database support expansion

## Summary

SchemaRAG now supports more database engines beyond the original MySQL and PostgreSQL focus (see provider and engine code for the exact current list).

## Supported types (reference)

| Database | Default port | Driver (typical) | Connection string (example) |
|----------|-------------|------------------|-----------------------------|
| MySQL | 3306 | pymysql | `mysql+pymysql://user:password@host:port/database` |
| PostgreSQL | 5432 | psycopg2-binary | `postgresql://user:password@host:port/database` |
| Microsoft SQL Server | 1433 | pymssql | `mssql+pymssql://user:password@host:port/database` |
| Oracle | 1521 | oracledb | `oracle+oracledb://user:password@host:port/database` |
| Dameng (DM) | 5236 | dm+pymysql | `dm+pymysql://user:password@host:port/database` |

## Files touched (high level)

### `provider/provider.yaml`
- Additional `db_type` options (e.g. SQLite, SQL Server, Oracle, Dameng)  
- Default port hints in UI copy  
- SQLite-specific notes (no host/port/user/password required)  

### `provider/build_schema_rag.py`
- `_get_default_port()` (or equivalent) maps engine → default port  
- Credential validation: SQLite uses file path; others need full connection fields  
- Config builder picks sensible defaults per engine  

### `core/m_schema/schema_engine.py`
- `init_mschema()` (or equivalent) handles dialect-specific schema/catalog rules  
- SQLite: no named schema layer  
- SQL Server / Oracle / Dameng: follow each engine’s conventions  

### `requirements.txt` / `pyproject.toml`
- Optional drivers such as `pymssql`, `oracledb`; Dameng driver may be optional/commented  

### Default port selection

When the user omits a port, the plugin can infer it:

```python
def _get_default_port(self, db_type: str) -> int:
    port_mapping = {
        "mysql": 3306,
        "postgresql": 5432,
        "mssql": 1433,
        "oracle": 1521,
        "dameng": 5236,
        "sqlite": 0,  # not used for SQLite file URLs
    }
    return port_mapping.get(db_type, 3306)
```

## Tests

`test/test_database_support.py` smoke-checks connection string generation for several engines.

## User configuration

1. Choose the database type in the provider UI.  
2. Fill connection fields for that engine.  
3. For SQLite, provide the database file path; other fields may be ignored.  
4. For other engines, use standard host/port/user/password/database values.  

The plugin adapts connection construction per engine.
