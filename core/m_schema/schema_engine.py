import logging
import time
from typing import Dict, List, Optional

from sqlalchemy import MetaData, Table, select
from sqlalchemy.engine import Engine

from core.m_schema.m_schema import MSchema
from core.m_schema.sql_database import SQLDatabase
from utils import examples_to_str


def _format_eta(seconds: float) -> str:
    if seconds <= 0 or seconds > 86400 * 14:
        return "n/d"
    sec = int(seconds)
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


class SchemaEngine(SQLDatabase):
    def __init__(
        self,
        engine: Engine,
        schema: Optional[str] = None,
        metadata: Optional[MetaData] = None,
        ignore_tables: Optional[List[str]] = None,
        include_tables: Optional[List[str]] = None,
        sample_rows_in_table_info: int = 3,
        indexes_in_table_info: bool = False,
        custom_table_info: Optional[dict] = None,
        view_support: bool = False,
        max_string_length: int = 300,
        mschema: Optional[MSchema] = None,
        db_name: Optional[str] = "",
        logger: Optional[logging.Logger] = None,
    ):
        self._logger = logger or logging.getLogger(__name__)
        t_init = time.monotonic()
        super().__init__(
            engine,
            schema,
            metadata,
            ignore_tables,
            include_tables,
            sample_rows_in_table_info,
            indexes_in_table_info,
            custom_table_info,
            view_support,
            max_string_length,
        )

        self._db_name = db_name
        # Dictionary to store table names and their corresponding schema
        self._tables_schemas: Dict[
            str, str
        ] = {}  # For MySQL and similar databases, if no schema is specified but db_name is provided,
        # use db_name as the schema to avoid getting tables from all databases
        if schema is None and db_name:
            if self._engine.dialect.name in ["mysql", "doris"]:
                # MySQL and Doris: database name acts as schema
                schema = db_name
            elif self._engine.dialect.name == "postgresql":
                # For PostgreSQL, use 'public' as default schema
                schema = "public"
            elif self._engine.dialect.name == "mssql":
                # For SQL Server, use 'dbo' as default schema
                schema = "dbo"

        # If a schema is specified, filter by that schema and store that value for every table.
        if schema:
            self._usable_tables = [
                table_name
                for table_name in self._usable_tables
                if self._inspector.has_table(table_name, schema)
            ]
            for table_name in self._usable_tables:
                self._tables_schemas[table_name] = schema
        else:
            all_tables = []
            # Iterate through all available schemas
            for s in self.get_schema_names():
                tables = self._inspector.get_table_names(schema=s)
                all_tables.extend(tables)
                for table in tables:
                    self._tables_schemas[table] = s
            self._usable_tables = all_tables

        self._dialect = engine.dialect.name
        n_after_filter = len(self._usable_tables)
        self._logger.info(
            "[schema_engine] phase=after_schema_filter dialect=%s db_name=%r "
            "effective_schema=%r tables_in_build=%d init_elapsed_s=%.2f",
            self._dialect,
            db_name,
            schema,
            n_after_filter,
            time.monotonic() - t_init,
        )

        if mschema is not None:
            self._mschema = mschema
        else:
            self._mschema = MSchema(db_id=db_name, schema=schema)
            self.init_mschema()

        self._logger.info(
            "[schema_engine] phase=engine_ready total_elapsed_s=%.2f",
            time.monotonic() - t_init,
        )

    @property
    def mschema(self) -> MSchema:
        """Return M-Schema"""
        return self._mschema

    def get_pk_constraint(self, table_name: str) -> List[str]:
        return self._inspector.get_pk_constraint(
            table_name, self._tables_schemas[table_name]
        )["constrained_columns"]

    def get_table_comment(self, table_name: str):
        try:
            return self._inspector.get_table_comment(
                table_name, self._tables_schemas[table_name]
            )["text"]
        except Exception:  # sqlite does not support comments
            return ""

    def default_schema_name(self) -> Optional[str]:
        return self._inspector.default_schema_name

    def get_schema_names(self) -> List[str]:
        return self._inspector.get_schema_names()

    def get_foreign_keys(self, table_name: str):
        return self._inspector.get_foreign_keys(
            table_name, self._tables_schemas[table_name]
        )

    def get_unique_constraints(self, table_name: str):
        return self._inspector.get_unique_constraints(
            table_name, self._tables_schemas[table_name]
        )

    def fectch_distinct_values(
        self, table_name: str, column_name: str, max_num: int = 5
    ):
        table = Table(
            table_name,
            self.metadata_obj,
            autoload_with=self._engine,
            schema=self._tables_schemas[table_name],
        )
        # Construct SELECT DISTINCT query
        query = select(table.c[column_name]).distinct().limit(max_num)
        values = []
        with self._engine.connect() as connection:
            result = connection.execute(query)
            distinct_values = result.fetchall()
            for value in distinct_values:
                if value[0] is not None and value[0] != "":
                    values.append(value[0])
        return values

    def init_mschema(self):
        total = len(self._usable_tables)
        t_build = time.monotonic()
        self._logger.info(
            "[schema_engine] phase=mschema_build_start tables=%d "
            "(each column runs one DISTINCT sample; this dominates duration on large DBs)",
            total,
        )

        progress_every = max(1, min(50, total // 20 or 1))

        for idx, table_name in enumerate(self._usable_tables):
            t_table = time.monotonic()
            obj_index = idx + 1
            schema_name = self._tables_schemas[table_name]
            qualified = (
                f"{schema_name}.{table_name}"
                if schema_name
                else table_name
            )
            self._logger.info(
                "[schema_engine] phase=mschema_object "
                "object=%d/%d qualified_name=%r inspector_table=%r schema=%r",
                obj_index,
                total,
                qualified,
                table_name,
                schema_name,
            )

            table_comment = self.get_table_comment(table_name)
            table_comment = (
                "" if table_comment is None else table_comment.strip()
            )  # For different database types, handle schema naming
            dialect_name = self._engine.dialect.name

            if dialect_name in ["mysql", "doris"] and schema_name == self._db_name:
                # MySQL and Doris: schema equals DB name; omit prefix in table id
                table_with_schema = table_name
            elif dialect_name == "postgresql" and schema_name == "public":
                table_with_schema = table_name
            elif dialect_name in ["mssql", "oracle", "dameng"]:
                # For SQL Server, Oracle, and Dameng, include schema if not default
                if schema_name and schema_name.lower() not in ["dbo", "public", "main"]:
                    table_with_schema = schema_name + "." + table_name
                else:
                    table_with_schema = table_name
            else:
                table_with_schema = schema_name + "." + table_name
            self._mschema.add_table(table_with_schema, fields={}, comment=table_comment)
            pks = self.get_pk_constraint(table_name)

            fks = self.get_foreign_keys(table_name)
            for fk in fks:
                referred_schema = fk["referred_schema"]
                for c, r in zip(fk["constrained_columns"], fk["referred_columns"]):
                    self._mschema.add_foreign_key(
                        table_with_schema, c, referred_schema, fk["referred_table"], r
                    )

            fields = self._inspector.get_columns(
                table_name, schema=self._tables_schemas[table_name]
            )
            n_cols = len(fields)
            # Log column DISTINCT progress: wide tables ~8 steps; narrow tables 1ª e última coluna.
            col_log_step = max(1, n_cols // 8) if n_cols > 16 else None

            for col_idx, field in enumerate(fields, start=1):
                field_type = f"{field['type']!s}"
                field_name = field["name"]
                primary_key = field_name in pks
                field_comment = field.get("comment", None)
                field_comment = "" if field_comment is None else field_comment.strip()
                autoincrement = field.get("autoincrement", False)
                default = field.get("default", None)
                if default is not None:
                    default = f"{default}"

                log_col = False
                if n_cols == 0:
                    pass
                elif col_log_step is not None:
                    log_col = (
                        col_idx == 1
                        or col_idx == n_cols
                        or col_idx % col_log_step == 0
                    )
                else:
                    log_col = col_idx == 1 or col_idx == n_cols

                if log_col:
                    self._logger.info(
                        "[schema_engine] phase=column_distinct_sample "
                        "object=%d/%d qualified_name=%r column=%d/%d column_name=%r",
                        obj_index,
                        total,
                        table_with_schema,
                        col_idx,
                        n_cols,
                        field_name,
                    )

                try:
                    examples = self.fectch_distinct_values(table_name, field_name, 5)
                except Exception as ex:
                    self._logger.warning(
                        "[schema_engine] phase=distinct_sample table=%s column=%s error=%s",
                        table_with_schema,
                        field_name,
                        ex,
                    )
                    examples = []
                examples = examples_to_str(examples)

                self._mschema.add_field(
                    table_with_schema,
                    field_name,
                    field_type=field_type,
                    primary_key=primary_key,
                    nullable=field["nullable"],
                    default=default,
                    autoincrement=autoincrement,
                    comment=field_comment,
                    examples=examples,
                )

            done = idx + 1
            table_elapsed = time.monotonic() - t_table
            elapsed = time.monotonic() - t_build
            rate = done / elapsed if elapsed > 0 else 0.0
            remaining = total - done
            eta_s = (remaining / rate) if rate > 0 else 0.0

            if done == 1 or done % progress_every == 0 or done == total:
                self._logger.info(
                    "[schema_engine] phase=mschema_object_done "
                    "object=%d/%d last_qualified_name=%r columns=%d "
                    "last_table_s=%.2f elapsed_s=%.1f eta_remaining≈%s",
                    done,
                    total,
                    table_with_schema,
                    n_cols,
                    table_elapsed,
                    elapsed,
                    _format_eta(eta_s),
                )

        self._logger.info(
            "[schema_engine] phase=mschema_build_done tables=%d total_elapsed_s=%.2f",
            total,
            time.monotonic() - t_build,
        )
