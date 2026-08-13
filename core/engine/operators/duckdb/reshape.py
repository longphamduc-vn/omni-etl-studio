from typing import Any, Dict
from core.engine.operators.base import BaseOperator
from core.engine.operators.registry import OperatorRegistry
from core.storage.context import PipelineContext


@OperatorRegistry.register("pivot")
class DuckDBPivotOperator(BaseOperator):
    """Executes SQL PIVOT operations in DuckDB."""

    def execute(self, table_name: str, params: Dict[str, Any], context: PipelineContext) -> str:
        on_col = params.get("on")
        using_col = params.get("using")
        group_by = params.get("group_by", [])

        full_table = f"{context.schema_name}.{table_name}"
        group_clause = f"GROUP BY {', '.join([f'\"{col}\"' for col in group_by])}" if group_by else ""

        query = f"""
            CREATE OR REPLACE TABLE {full_table} AS
            PIVOT {full_table}
            ON "{on_col}"
            USING SUM("{using_col}")
            {group_clause};
        """
        context.execute_sql(query)
        return table_name


@OperatorRegistry.register("unpivot")
class DuckDBUnpivotOperator(BaseOperator):
    """Executes SQL UNPIVOT (Melt) operations in DuckDB."""

    def execute(self, table_name: str, params: Dict[str, Any], context: PipelineContext) -> str:
        on_cols = params.get("on", [])
        full_table = f"{context.schema_name}.{table_name}"
        cols_str = ", ".join([f'"{col}"' for col in on_cols])

        query = f"""
            CREATE OR REPLACE TABLE {full_table} AS
            UNPIVOT {full_table}
            ON {cols_str};
        """
        context.execute_sql(query)
        return table_name