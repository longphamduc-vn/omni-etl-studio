from typing import Any, Dict
from core.engine.operators.base import BaseOperator
from core.engine.operators.registry import OperatorRegistry
from core.storage.context import PipelineContext


@OperatorRegistry.register("join")
class DuckDBJoinOperator(BaseOperator):
    """Executes SQL JOIN operations (INNER, LEFT, RIGHT, FULL) between two DuckDB tables."""

    def execute(self, table_name: str, params: Dict[str, Any], context: PipelineContext) -> str:
        right_table = params.get("right_table")
        join_type = params.get("how", "LEFT").upper()  # INNER, LEFT, RIGHT, FULL
        on_keys = params.get("on", [])  # e.g., ["product_id"] or {"left_key": "right_key"}
        select_cols = params.get("select", "*")  # e.g., "t1.*, t2.price"

        if not right_table:
            raise ValueError("DuckDBJoinOperator requires 'right_table' parameter.")

        left_full = f"{context.schema_name}.{table_name}"
        right_full = f"{context.schema_name}.{right_table}"

        # Build ON condition
        if isinstance(on_keys, list):
            on_clause = " AND ".join([f't1."{k}" = t2."{k}"' for k in on_keys])
        elif isinstance(on_keys, dict):
            on_clause = " AND ".join([f't1."{lk}" = t2."{rk}"' for lk, rk in on_keys.items()])
        else:
            raise ValueError("Parameter 'on' must be a list of column names or a key-mapping dictionary.")

        query = f"""
            CREATE OR REPLACE TABLE {left_full} AS
            SELECT {select_cols}
            FROM {left_full} t1
            {join_type} JOIN {right_full} t2
            ON {on_clause};
        """
        context.execute_sql(query)
        return table_name