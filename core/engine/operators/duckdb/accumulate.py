# ==============================================================================
# Filepath: core/engine/operators/duckdb/accumulate.py
# Updated_at: 2026-08-16 18:13:00
# Description: Persistent data accumulation operator using DuckDB QUALIFY clause.
# ==============================================================================

from typing import Any, Dict
from core.common.logger import log
from core.engine.operators.base import BaseOperator
from core.engine.operators.registry import OperatorRegistry
from core.storage.context import PipelineContext


@OperatorRegistry.register("accumulate_data")
class AccumulateDataOperator(BaseOperator):
    """Accumulates step data into persistent storage using Native DuckDB QUALIFY upsert."""

    def execute(self, table_name: str, params: Dict[str, Any], context: PipelineContext) -> str:
        history_table = params.get("target_history_table", "ds_history")
        dedup_list = params.get("dedup_keys", ["product_id"])
        order_by = params.get("order_by", "created_date DESC")

        dedup_keys = ", ".join([f'"{k}"' for k in dedup_list])
        curr_table = f"{context.schema_name}.{table_name}" if getattr(context, "schema_name", None) else table_name
        shared_schema = getattr(context, "shared_schema", "shared_storage")
        store_table = f"{shared_schema}.{history_table}"

        # 1. Initialize persistent storage table if not exists
        init_sql = f"CREATE TABLE IF NOT EXISTS {store_table} AS SELECT * FROM {curr_table} WHERE 1=0;"
        context.execute_sql(init_sql)

        # 2. Auto-synchronize missing columns (Schema Evolution)
        try:
            sync_sql = f"ALTER TABLE {store_table} ADD COLUMNS FROM {curr_table};"
            context.execute_sql(sync_sql)
        except Exception:
            pass  # Ignored if schemas are already in sync

        # 3. Append current batch records by column names
        insert_sql = f"INSERT INTO {store_table} BY NAME SELECT * FROM {curr_table};"
        context.execute_sql(insert_sql)

        # 4. Native DuckDB Deduplication using QUALIFY
        dedup_sql = f"""
            CREATE OR REPLACE TABLE {store_table} AS 
            SELECT * FROM {store_table}
            QUALIFY ROW_NUMBER() OVER (PARTITION BY {dedup_keys} ORDER BY {order_by}) = 1;
        """
        log.info(f"[ACCUMULATE QUALIFY] {dedup_sql.strip()}")
        context.execute_sql(dedup_sql)

        # 5. Mirror deduplicated state back to current step output dataset
        sync_back_sql = f"CREATE OR REPLACE TABLE {curr_table} AS SELECT * FROM {store_table};"
        context.execute_sql(sync_back_sql)

        return table_name