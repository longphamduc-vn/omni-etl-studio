from typing import Any, Dict
from core.engine.operators.base import BaseOperator
from core.engine.operators.registry import OperatorRegistry
from core.storage.context import PipelineContext


@OperatorRegistry.register("group_by")
class DuckDBGroupByOperator(BaseOperator):
    """Executes SQL GROUP BY aggregations dynamically in DuckDB with automatic type casting for numeric operations."""

    def execute(self, table_name: str, params: Dict[str, Any], context: PipelineContext) -> str:
        by_cols = params.get("by", [])
        agg_map = params.get("agg", {})  # e.g., {"quantity": "SUM", "score": "AVG"}

        full_table = f"{context.schema_name}.{table_name}"
        by_clause = ", ".join([f'"{col}"' for col in by_cols]) if by_cols else ""

        agg_exprs = []
        for col, func in agg_map.items():
            func_upper = func.upper()
            # Áp dụng TRY_CAST cho các hàm toán học để tránh lỗi sum(VARCHAR)
            if func_upper in ["SUM", "AVG", "MEAN", "MEDIAN", "STDDEV"]:
                agg_exprs.append(f'{func_upper}(TRY_CAST("{col}" AS DOUBLE)) AS "{col}_{func.lower()}"')
            else:
                agg_exprs.append(f'{func_upper}("{col}") AS "{col}_{func.lower()}"')

        if by_cols:
            select_clause = f"{by_clause}, " + ", ".join(agg_exprs) if agg_exprs else by_clause
            group_clause = f"GROUP BY {by_clause}"
        else:
            select_clause = ", ".join(agg_exprs)
            group_clause = ""

        query = f"CREATE OR REPLACE TABLE {full_table} AS SELECT {select_clause} FROM {full_table} {group_clause};"
        context.execute_sql(query)
        return table_name