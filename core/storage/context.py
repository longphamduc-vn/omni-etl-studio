import re
import duckdb
import pandas as pd
from typing import Optional
from core.common.exceptions import StorageError
from core.common.logger import log


class PipelineContext:
    """Manages DuckDB storage with a global persistent schema for cross-session data accumulation."""

    DB_FILE = "omni_etl_studio.duckdb"
    SHARED_SCHEMA = "shared_storage"

    def __init__(self, pipeline_id: Optional[str] = None):
        self.pipeline_id = pipeline_id or "default_session"
        clean_id = re.sub(r'[^a-zA-Z0-9_]', '_', self.pipeline_id)
        self.schema_name = f"ns_{clean_id}"
        self.shared_schema = self.SHARED_SCHEMA
        
        try:
            # Mở kết nối vĩnh viễn tới file DuckDB vật lý trên đĩa
            self.conn = duckdb.connect(database=self.DB_FILE)
            self._init_schema()
        except Exception as e:
            raise StorageError(f"Failed to initialize DuckDB storage context: {str(e)}")

    def _init_schema(self):
        """Initializes runtime execution schema and the persistent shared storage schema."""
        self.conn.execute(f"CREATE SCHEMA IF NOT EXISTS {self.schema_name};")
        self.conn.execute(f"CREATE SCHEMA IF NOT EXISTS {self.shared_schema};")

    def save_dataframe(self, table_name: str, df: pd.DataFrame, if_exists: str = "replace"):
        full_table = f"{self.schema_name}.{table_name}"
        try:
            self.conn.register("temp_df", df)
            try:
                if if_exists == "replace":
                    self.conn.execute(f"CREATE OR REPLACE TABLE {full_table} AS SELECT * FROM temp_df;")
                elif if_exists == "append":
                    self.conn.execute(f"INSERT INTO {full_table} SELECT * FROM temp_df;")
            finally:
                self.conn.unregister("temp_df")
        except Exception as e:
            raise StorageError(f"Failed to save DataFrame into table {full_table}: {str(e)}")

    def get_dataframe(self, table_name: str) -> pd.DataFrame:
        """Searches active execution schema first, then falls back to persistent shared_storage."""
        full_table = f"{self.schema_name}.{table_name}"
        shared_table = f"{self.shared_schema}.{table_name}"
        try:
            check_exec = self.conn.execute(f"""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = '{self.schema_name}' AND table_name = '{table_name}';
            """).df()
            if not check_exec.empty:
                return self.conn.execute(f"SELECT * FROM {full_table};").df()

            check_shared = self.conn.execute(f"""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = '{self.shared_schema}' AND table_name = '{table_name}';
            """).df()
            if not check_shared.empty:
                return self.conn.execute(f"SELECT * FROM {shared_table};").df()

            return pd.DataFrame()
        except Exception as e:
            raise StorageError(f"Failed to fetch table {table_name}: {str(e)}")

    def execute_sql(self, query: str) -> pd.DataFrame:
        try:
            return self.conn.execute(query).df()
        except Exception as e:
            raise StorageError(f"SQL execution error [{query}]: {str(e)}")

    def clean_temporary_schemas(self):
        """Safely cleans old temporary run schemas while preserving shared_storage."""
        try:
            schemas_df = self.conn.execute("""
                SELECT schema_name FROM information_schema.schemata 
                WHERE schema_name LIKE 'ns_run_%';
            """).df()
            if not schemas_df.empty:
                for s_name in schemas_df["schema_name"].tolist():
                    self.conn.execute(f"DROP SCHEMA IF EXISTS {s_name} CASCADE;")
                log.info("Cleaned up temporary execution schemas.")
        except Exception as e:
            log.warning(f"Error cleaning temporary schemas: {str(e)}")

    def close(self):
        """Closes connection without deleting persistent historical data."""
        try:
            self.conn.close()
        except Exception:
            pass