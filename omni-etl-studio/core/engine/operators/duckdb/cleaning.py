from typing import Any, Dict
from core.engine.operators.base import BaseOperator
from core.engine.operators.registry import OperatorRegistry
from core.storage.context import PipelineContext


@OperatorRegistry.register("deduplicate")
class DuckDBDeduplicateOperator(BaseOperator):
    """Executes row deduplication using DuckDB QUALIFY & ROW_NUMBER()."""

    def execute(self, table_name: str, params: Dict[str, Any], context: PipelineContext) -> str:
        subset = params.get("subset", [])
        full_table = f"{context.schema_name}.{table_name}"

        if subset:
            cols_str = ", ".join([f'"{col}"' for col in subset])
            query = f"""
                CREATE OR REPLACE TABLE {full_table} AS
                SELECT * FROM {full_table}
                QUALIFY ROW_NUMBER() OVER (PARTITION BY {cols_str}) = 1;
            """
        else:
            query = f"CREATE OR REPLACE TABLE {full_table} AS SELECT DISTINCT * FROM {full_table};"

        context.execute_sql(query)
        return table_name


@OperatorRegistry.register("handle_nulls")
class DuckDBHandleNullsOperator(BaseOperator):
    """Handles NULL values in DuckDB tables by dropping incomplete rows."""

    def execute(self, table_name: str, params: Dict[str, Any], context: PipelineContext) -> str:
        action = params.get("action", "drop")
        full_table = f"{context.schema_name}.{table_name}"

        if action == "drop":
            subset = params.get("subset", [])
            if subset:
                where_clause = " AND ".join([f'"{col}" IS NOT NULL' for col in subset])
            else:
                cols_df = context.conn.execute(f"DESCRIBE SELECT * FROM {full_table};").df()
                cols = cols_df["column_name"].tolist()
                where_clause = " AND ".join([f'"{col}" IS NOT NULL' for col in cols])

            query = f"CREATE OR REPLACE TABLE {full_table} AS SELECT * FROM {full_table} WHERE {where_clause};"
            context.execute_sql(query)

        return table_name