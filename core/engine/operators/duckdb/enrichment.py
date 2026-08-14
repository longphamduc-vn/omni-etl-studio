from core.common.logger import log
from core.engine.operators.base import BaseOperator
from core.engine.operators.registry import OperatorRegistry
from core.storage.context import PipelineContext


@OperatorRegistry.register("add_date_column")
class AddDateColumnOperator(BaseOperator):
    """Operator to compute and append a date/timestamp column to the active DuckDB table."""

    def execute(self, table_name: str, params: dict, context: PipelineContext) -> str:
        target_column = params.get("target_column", "created_date")
        date_source = params.get("date_source", "current_date")
        sql_expr = "CURRENT_TIMESTAMP" if date_source == "current_timestamp" else "CURRENT_DATE"

        # Định danh bảng chuẩn kèm schema namespace (e.g., ns_run_xxx.ds_step2_product_details)
        full_table = f"{context.schema_name}.{table_name}" if context.schema_name else table_name

        check_df = context.execute_sql(f"SELECT * FROM {full_table} LIMIT 0;")
        if target_column not in check_df.columns:
            query = f"""
            CREATE OR REPLACE TABLE {full_table} AS 
            SELECT *, {sql_expr} AS {target_column} 
            FROM {full_table};
            """
            context.execute_sql(query)
            log.info(f"Added date column '{target_column}' to table '{full_table}'")

        return table_name


@OperatorRegistry.register("accumulate_data")
class AccumulateDataOperator(BaseOperator):
    """Operator to append current table records into a historical DuckDB table using UNION ALL BY NAME."""

    def execute(self, table_name: str, params: dict, context: PipelineContext) -> str:
        target_history_table = params.get("target_history_table", "ds_historical_data")
        
        full_table = f"{context.schema_name}.{table_name}" if context.schema_name else table_name
        full_hist_table = f"{context.schema_name}.{target_history_table}" if context.schema_name else target_history_table

        # 1. Kiểm tra nếu bảng lịch sử chưa tồn tại -> Khởi tạo với đầy đủ các cột mới (bao gồm created_date)
        context.execute_sql(f"""
            CREATE TABLE IF NOT EXISTS {full_hist_table} AS 
            SELECT * FROM {full_table};
        """)

        # 2. Nối dữ liệu an toàn theo TÊN CỘT (UNION ALL BY NAME tự khớp cả các cột mới)
        context.execute_sql(f"""
            CREATE OR REPLACE TABLE {full_hist_table} AS 
            SELECT * FROM {full_hist_table}
            UNION ALL BY NAME
            SELECT * FROM {full_table};
        """)

        # 3. Trả về dữ liệu đã tích lũy kèm đầy đủ schema mới
        context.execute_sql(f"CREATE OR REPLACE TABLE {full_table} AS SELECT * FROM {full_hist_table};")
        log.info(f"Accumulated dataset '{full_table}' into historical table '{full_hist_table}'")

        return table_name

@OperatorRegistry.register("sql_transform")
class SqlTransformOperator(BaseOperator):
    """Executes a custom SELECT projection against the active DuckDB table safely with namespace."""

    def execute(self, table_name: str, params: dict, context: PipelineContext) -> str:
        select_expr = params.get("select_expression", "*")
        full_table = f"{context.schema_name}.{table_name}" if context.schema_name else table_name

        query = f"""
        CREATE OR REPLACE TABLE {full_table} AS 
        SELECT {select_expr} 
        FROM {full_table};
        """
        context.execute_sql(query)
        log.info(f"Applied custom SQL transformation on table '{full_table}' with expression: {select_expr}")

        return table_name