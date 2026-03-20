import re
from typing import Dict, List, Tuple, Optional
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError, OperationalError, ProgrammingError
from urllib.parse import quote_plus

# Optional Dameng driver + SQLAlchemy dialect
try:
    import dmPython
    import sqlalchemy_dm

    DAMENG_AVAILABLE = True
except ImportError:
    DAMENG_AVAILABLE = False


class DatabaseService:
    """
    Database access via SQLAlchemy: connections, pooling, and query execution.

    Supported engines:
    - MySQL
    - PostgreSQL
    - SQL Server (MSSQL)
    - Oracle
    - DamengDB
    """

    DB_DRIVERS = {
        "mysql": "mysql+pymysql",
        "postgresql": "postgresql+psycopg2",
        "mssql": "mssql+pymssql",
        "oracle": "oracle+oracledb",
        "dameng": "dm+dmPython",
        "doris": "doris+pymysql",  # Apache Doris (MySQL protocol)
    }

    def __init__(self):
        """Initialize service state."""
        self._engine_cache: Dict[str, Engine] = {}

    def _build_connection_uri(
        self, db_type: str, host: str, port: int, user: str, password: str, dbname: str
    ) -> str:
        """
        Build a SQLAlchemy database URI.

        Args:
            db_type: Engine key (mysql, postgresql, ...)
            host: Hostname
            port: Port
            user: Username
            password: Password
            dbname: Database / service name

        Returns:
            SQLAlchemy URI string

        Raises:
            ValueError: Unknown db_type
        """
        if db_type not in self.DB_DRIVERS:
            raise ValueError(f"Unsupported database type: {db_type}")

        encoded_password = quote_plus(password)
        encoded_user = quote_plus(user)

        driver = self.DB_DRIVERS[db_type]

        if db_type == "oracle":
            return f"{driver}://{encoded_user}:{encoded_password}@{host}:{port}/?service_name={dbname}"
        elif db_type == "dameng":
            if not DAMENG_AVAILABLE:
                raise ValueError(
                    "DamengDB support requires dmPython package to be installed"
                )
            return (
                f"{driver}://{encoded_user}:{encoded_password}@{host}:{port}/{dbname}"
            )
        else:
            return (
                f"{driver}://{encoded_user}:{encoded_password}@{host}:{port}/{dbname}"
            )

    def _get_or_create_engine(
        self, db_type: str, host: str, port: int, user: str, password: str, dbname: str
    ) -> Engine:
        """
        Return a cached SQLAlchemy Engine for this connection tuple.

        Args:
            db_type: Engine key
            host: Hostname
            port: Port
            user: Username
            password: Password
            dbname: Database name

        Returns:
            SQLAlchemy Engine
        """
        cache_key = f"{db_type}://{user}@{host}:{port}/{dbname}"

        if cache_key not in self._engine_cache:
            uri = self._build_connection_uri(
                db_type, host, port, user, password, dbname
            )

            engine_args = {
                "pool_pre_ping": True,
                "pool_recycle": 3600,
                "echo": False,
            }

            if db_type == "mysql" or db_type == "doris":
                engine_args["connect_args"] = {"charset": "utf8mb4"}
            elif db_type == "mssql":
                engine_args["connect_args"] = {"charset": "utf8"}
            elif db_type == "oracle":
                engine_args["connect_args"] = {"thick_mode_dsn_passthrough": False}
            elif db_type == "dameng":
                engine_args["connect_args"] = {
                    "encoding": "UTF-8",
                }

            self._engine_cache[cache_key] = create_engine(uri, **engine_args)

        return self._engine_cache[cache_key]

    def execute_query(
        self,
        db_type: str,
        host: str,
        port: int,
        user: str,
        password: str,
        dbname: str,
        query: str,
    ) -> Tuple[List[Dict], List[str]]:
        """
        Execute a SQL statement and return rows + column names.

        Args:
            db_type: mysql | postgresql | mssql | oracle | dameng | doris
            host: Host
            port: Port
            user: User
            password: Password
            dbname: Database name
            query: SQL text (markdown fences stripped if present)

        Returns:
            (list of row dicts, column names)

        Raises:
            ValueError: Empty SQL or unexpected failure
            SQLAlchemyError: Driver / DB errors
        """
        match = re.search(r"```(?:sql)?\s*(.*?)\s*```", query, re.DOTALL)
        if match:
            cleaned_sql = match.group(1).strip()
        else:
            cleaned_sql = query.strip()

        if not cleaned_sql:
            raise ValueError("SQL query cannot be empty.")

        try:
            engine = self._get_or_create_engine(
                db_type, host, port, user, password, dbname
            )

            with engine.connect() as connection:
                result = connection.execute(text(cleaned_sql))

                if result.returns_rows:
                    columns = list(result.keys())
                    rows = result.fetchall()
                    results = [dict(zip(columns, row)) for row in rows]
                    return results, columns
                else:
                    return [{"status": "success", "rows_affected": result.rowcount}], [
                        "result"
                    ]

        except (OperationalError, ProgrammingError) as e:
            raise SQLAlchemyError(f"Database operation failed: {str(e)}") from e
        except SQLAlchemyError as e:
            raise SQLAlchemyError(f"SQLAlchemy error: {str(e)}") from e
        except Exception as e:
            raise ValueError(
                f"Unexpected error during query execution: {str(e)}"
            ) from e

    def close_all_connections(self):
        """Dispose all cached engines."""
        for engine in self._engine_cache.values():
            engine.dispose()
        self._engine_cache.clear()

    def _format_output(
        self, results: List[Dict], columns: List[str], format_type: str
    ) -> str:
        """
        Serialize query results to JSON or Markdown.

        Args:
            results: Row dicts
            columns: Column order
            format_type: 'json' or 'md'

        Returns:
            Formatted string
        """
        if not results:
            return "Query executed successfully, but returned no results."

        df = pd.DataFrame(results, columns=columns)

        if format_type == "json":
            return df.to_json(orient="records", indent=4, force_ascii=False)
        elif format_type == "md":
            return df.to_markdown(index=False)
        else:
            return "Unsupported output format. Please use 'json' or 'md'."

    def __del__(self):
        """Best-effort cleanup on GC."""
        try:
            self.close_all_connections()
        except Exception:
            pass
