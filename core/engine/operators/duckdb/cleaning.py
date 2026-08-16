from typing import Any, Dict
from core.engine.operators.base import BaseOperator
from core.engine.operators.registry import OperatorRegistry
from core.storage.context import PipelineContext


@OperatorRegistry.register("deduplicate")
class DuckDBDeduplicateOperator(BaseOperator):
    """Executes row deduplication using DuckDB QUALIFY & ROW_NUMBER()."""

    def execute(self, table_name: str, params: Dict[str, Any], context: PipelineContext) -> str:
        subset = params.get("subset", [])
        order_by = params.get("order_by", "")
        full_table = f"{context.schema_name}.{table_name}" if getattr(context, "schema_name", None) else table_name

        if subset:
            cols_str = ", ".join([f'"{col}"' for col in subset])
            order_clause = f"ORDER BY {order_by}" if order_by else ""
            query = f"""
                CREATE OR REPLACE TABLE {full_table} AS
                SELECT * FROM {full_table}
                QUALIFY ROW_NUMBER() OVER (PARTITION BY {cols_str} {order_clause}) = 1;
            """
        else:
            query = f"CREATE OR REPLACE TABLE {full_table} AS SELECT DISTINCT * FROM {full_table};"

        context.execute_sql(query)
        return table_name


@OperatorRegistry.register("handle_nulls")
class DuckDBHandleNullsOperator(BaseOperator):
    """Handles NULL values in DuckDB tables by dropping incomplete rows or filling default values."""

    def execute(self, table_name: str, params: Dict[str, Any], context: PipelineContext) -> str:
        # Chuẩn hóa: Dùng duy nhất 'strategy' (drop / fill)
        strategy = params.get("strategy", "drop")
        full_table = f"{context.schema_name}.{table_name}" if getattr(context, "schema_name", None) else table_name

        if strategy == "drop":
            subset = params.get("subset", [])
            if subset:
                where_clause = " AND ".join([f'"{col}" IS NOT NULL' for col in subset])
            else:
                cols_df = context.execute_sql(f"DESCRIBE SELECT * FROM {full_table};")
                cols = cols_df["column_name"].tolist() if hasattr(cols_df, "columns") else []
                where_clause = " AND ".join([f'"{col}" IS NOT NULL' for col in cols]) if cols else "1=1"

            query = f"CREATE OR REPLACE TABLE {full_table} AS SELECT * FROM {full_table} WHERE {where_clause};"
            context.execute_sql(query)

        elif strategy == "fill":
            fill_map = params.get("fill_value", {})
            if fill_map:
                set_clauses = [f'"{col}" = COALESCE("{col}", \'{val}\')' for col, val in fill_map.items()]
                query = f"UPDATE {full_table} SET {', '.join(set_clauses)};"
                context.execute_sql(query)

        return table_name


@OperatorRegistry.register("select_rename")
class DuckDBSelectRenameOperator(BaseOperator):
    """Selects specific columns, renames fields, and casts column data types in DuckDB."""

    def execute(self, table_name: str, params: Dict[str, Any], context: PipelineContext) -> str:
        columns_map = params.get("columns", {})  # e.g., {"old_name": "new_name"}
        casts_map = params.get("casts", {})      # e.g., {"price": "DOUBLE", "age": "INTEGER"}
        keep_cols = params.get("keep", [])

        full_table = f"{context.schema_name}.{table_name}" if getattr(context, "schema_name", None) else table_name

        if keep_cols:
            select_exprs = []
            for col in keep_cols:
                target_name = columns_map.get(col, col)
                if col in casts_map:
                    select_exprs.append(f'TRY_CAST("{col}" AS {casts_map[col]}) AS "{target_name}"')
                else:
                    select_exprs.append(f'"{col}" AS "{target_name}"')
            select_str = ", ".join(select_exprs)
            query = f"CREATE OR REPLACE TABLE {full_table} AS SELECT {select_str} FROM {full_table};"
            context.execute_sql(query)
        else:
            for old_col, new_col in columns_map.items():
                context.execute_sql(f'ALTER TABLE {full_table} RENAME COLUMN "{old_col}" TO "{new_col}";')

        return table_name