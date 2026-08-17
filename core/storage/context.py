# ==============================================================================
# Filepath: core/storage/context.py
# Updated_at: 2026-08-16 17:38:52
# Description: Centralized execution context managing DuckDB connection and session state.
# ==============================================================================

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import duckdb
import pandas as pd

from config.settings import app_config
from core.common.logger import log


@dataclass
class PipelineContext:
    """Execution context managing DuckDB storage, auth sessions, and runtime states."""

    pipeline_id: str
    domain_path: str = "general"
    schema_name: str = ""
    shared_schema: str = app_config.shared_schema
    
    # Session state initialized by Workflow Init (Bearer token, user_id, etc.)
    session: Dict[str, Any] = field(default_factory=dict)
    
    # Global input data submitted from UI or API payloads
    input_data: Dict[str, Any] = field(default_factory=dict)
    
    # Central DuckDB connection instance
    conn: Optional[duckdb.DuckDBPyConnection] = None
    
    # Pipeline execution status: RUNNING, PAUSED_WAITING_RETRY, SUCCESS, FAILED
    exec_status: str = "RUNNING"
    
    # Business or system error detail payload when execution pauses
    error_info: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Initializes DuckDB connection and schema workspaces."""
        if not self.schema_name:
            self.schema_name = f"ns_{self.pipeline_id}"

        if self.conn is None:
            self.conn = duckdb.connect(database=app_config.db_path)

        # 1. Create temporary run schema workspace
        self.execute_sql(f"CREATE SCHEMA IF NOT EXISTS {self.schema_name};")
        
        # 2. Create persistent shared storage schema workspace
        self.execute_sql(f"CREATE SCHEMA IF NOT EXISTS {self.shared_schema};")
        
        log.info(f"[CONTEXT INIT] Workspace '{self.schema_name}' initialized for pipeline '{self.pipeline_id}'")

    def execute_sql(self, sql_query: str) -> Optional[pd.DataFrame]:
        """Executes raw SQL query against DuckDB connection and returns result as DataFrame."""
        if not self.conn:
            raise RuntimeError("DuckDB connection is closed or uninitialized.")

        try:
            rel = self.conn.execute(sql_query)
            if rel.description:
                return rel.df()
            return None
        except Exception as e:
            log.error(f"[DUCKDB EXEC ERROR] Query failed: {sql_query} | Error: {str(e)}")
            raise

    def save_dataframe(self, table_name: str, df: pd.DataFrame) -> str:
        """Registers a Pandas DataFrame directly as a DuckDB table inside current schema workspace."""
        full_table = f"{self.schema_name}.{table_name}"
        if df is None or df.empty:
            df = pd.DataFrame(columns=["status_msg"])

        self.conn.register("temp_df_view", df)
        self.execute_sql(f"CREATE OR REPLACE TABLE {full_table} AS SELECT * FROM temp_df_view;")
        self.conn.unregister("temp_df_view")
        
        log.info(f"[CONTEXT REGISTER] Table '{full_table}' saved with {len(df)} rows.")
        return table_name

    def get_dataframe(self, table_name: str) -> Optional[pd.DataFrame]:
        """Fetches table data from DuckDB schema workspace as a Pandas DataFrame."""
        full_table = f"{self.schema_name}.{table_name}"
        try:
            return self.execute_sql(f"SELECT * FROM {full_table};")
        except Exception:
            return None

    def close(self) -> None:
        """Safely closes active DuckDB database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            log.info(f"[CONTEXT CLOSED] Connection closed for pipeline '{self.pipeline_id}'")