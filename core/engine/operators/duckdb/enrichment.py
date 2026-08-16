import re
import streamlit as st
from core.common.logger import log
from core.engine.operators.base import BaseOperator
from core.engine.operators.registry import OperatorRegistry
from core.storage.context import PipelineContext

@OperatorRegistry.register("add_date_column")
class AddDateColumnOperator(BaseOperator):
    """Adds a computed date/timestamp column to the active DuckDB table."""

    def execute(self, table_name: str, params: dict, context: PipelineContext) -> str:
        target_column = params.get("target_column", "created_date")
        sql_expr = "CURRENT_TIMESTAMP" if params.get("date_source") == "current_timestamp" else "CURRENT_DATE"
        full_table = f"{context.schema_name}.{table_name}" if getattr(context, "schema_name", None) else table_name

        check_df = context.execute_sql(f"SELECT * FROM {full_table} LIMIT 0;")
        if target_column not in check_df.columns:
            query = f"CREATE OR REPLACE TABLE {full_table} AS SELECT *, {sql_expr} AS {target_column} FROM {full_table};"
            log.info(f"[SQL EXECUTE] {query}")
            context.execute_sql(query)

        return table_name


@OperatorRegistry.register("accumulate_data")
class AccumulateDataOperator(BaseOperator):
    """Accumulates new records, deduplicates, and replaces old records directly in persistent storage."""

    def execute(self, table_name: str, params: dict, context: PipelineContext) -> str:
        target_history_table = params.get("target_history_table", "ds_historical_data")
        dedup_keys = params.get("dedup_keys", ["product_id"])
        order_by = params.get("order_by", "created_date DESC")
        
        current_table = f"{context.schema_name}.{table_name}"
        shared_schema = getattr(context, "shared_schema", "shared_storage")
        persistent_table = f"{shared_schema}.{target_history_table}"

        init_sql = f"CREATE TABLE IF NOT EXISTS {persistent_table} AS SELECT * FROM {current_table} WHERE 1=0;"
        context.execute_sql(init_sql)

        try:
            context.execute_sql(f"ALTER TABLE {persistent_table} ADD COLUMNS FROM {current_table};")
        except Exception:
            pass

        insert_sql = f"INSERT INTO {persistent_table} BY NAME SELECT * FROM {current_table};"
        context.execute_sql(insert_sql)

        if dedup_keys:
            partition_str = ", ".join(dedup_keys)
            dedup_sql = f"""
                CREATE OR REPLACE TABLE {persistent_table} AS 
                SELECT * EXCLUDE (row_num) FROM (
                    SELECT *, ROW_NUMBER() OVER (PARTITION BY {partition_str} ORDER BY {order_by}) as row_num
                    FROM {persistent_table}
                ) WHERE row_num = 1;
            """
            context.execute_sql(dedup_sql)

        sync_sql = f"CREATE OR REPLACE TABLE {current_table} AS SELECT * FROM {persistent_table};"
        context.execute_sql(sync_sql)

        return table_name


@OperatorRegistry.register("sql_transform")
class SqlTransformOperator(BaseOperator):
    """Executes SQL transform by extracting search_table.product_id directly from context.inputs."""

    def execute(self, table_name: str, params: dict, context: PipelineContext) -> str:
        full_table = f"{context.schema_name}.{table_name}" if getattr(context, "schema_name", None) else table_name
        
        # 1. Lấy dữ liệu global_input chuẩn từ context.inputs vừa được gán ở runner.py
        global_input = getattr(context, "inputs", {}) or st.session_state.get("last_global_input", {})

        log.info(f"[FILTER DEBUG] Global Inputs available keys: {list(global_input.keys()) if isinstance(global_input, dict) else 'Not a dict'}")
        log.info(f"[FILTER DEBUG] Full Global Inputs Content: {global_input}")

        product_ids = []

        # 2. Đọc trực tiếp đường dẫn global_input.search_table.product_id
        if isinstance(global_input, dict) and "search_table" in global_input:
            search_table = global_input.get("search_table")
            if isinstance(search_table, list):
                product_ids = [
                    str(row.get("product_id")).strip() 
                    for row in search_table 
                    if isinstance(row, dict) and row.get("product_id") is not None
                ]
                log.info(f"[FILTER DEBUG] Resolved 'search_table.product_id' -> Extracted IDs: {product_ids}")

        # 3. Thực thi SQL WHERE CAST(product_id AS VARCHAR) IN ('SP-001', 'SP-002')
        if "where_clause" in params and product_ids:
            formatted_ids = ", ".join([f"'{pid}'" for pid in product_ids])
            sql = f"CREATE OR REPLACE TABLE {full_table} AS SELECT * FROM {full_table} WHERE CAST(product_id AS VARCHAR) IN ({formatted_ids});"
        elif "query" in params:
            sql = f"CREATE OR REPLACE TABLE {full_table} AS {params['query'].replace(table_name, full_table)};"
        else:
            log.warning("[SQL TRANSFORM WARNING] Product IDs empty. Retaining full accumulated step output.")
            sql = f"CREATE OR REPLACE TABLE {full_table} AS SELECT * FROM {full_table};"

        log.info(f"[SQL EXECUTE STEP] {sql}")
        context.execute_sql(sql)

        return table_name