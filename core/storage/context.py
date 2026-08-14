import re
import duckdb
import pandas as pd
from typing import Optional
from core.common.exceptions import StorageError
from core.common.logger import log


class PipelineContext:
    """Manages an isolated DuckDB schema namespace for each execution pipeline."""

    def __init__(self, pipeline_id: str, db_connection: Optional[duckdb.DuckDBPyConnection] = None):
        # Sanitize schema identifier to ensure safe SQL syntax execution
        clean_id = re.sub(r'[^a-zA-Z0-9_]', '_', pipeline_id)
        self.pipeline_id = pipeline_id
        self.schema_name = f"ns_{clean_id}"
        
        try:
            # self.conn = db_connection or duckdb.connect(database=":memory:")
            self.conn = duckdb.connect(database="omni_etl_studio.duckdb")
            self._init_schema()
        except Exception as e:
            raise StorageError(f"Failed to initialize DuckDB storage context: {str(e)}")

    def _init_schema(self):
        """Creates the isolated DuckDB schema namespace for the pipeline execution."""
        log.info(f"Initializing isolated DuckDB schema: {self.schema_name}")
        self.conn.execute(f"CREATE SCHEMA IF NOT EXISTS {self.schema_name};")

    def save_dataframe(self, table_name: str, df: pd.DataFrame, if_exists: str = "replace"):
        """Saves a Pandas DataFrame into the isolated DuckDB schema."""
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
            log.debug(f"Saved {len(df)} records into table {full_table}")
        except Exception as e:
            raise StorageError(f"Failed to save DataFrame into table {full_table}: {str(e)}")

    def get_dataframe(self, table_name: str) -> pd.DataFrame:
        """Fetches a table from DuckDB storage and converts it to a Pandas DataFrame."""
        full_table = f"{self.schema_name}.{table_name}"
        try:
            return self.conn.execute(f"SELECT * FROM {full_table};").df()
        except Exception as e:
            raise StorageError(f"Failed to fetch table {full_table}: {str(e)}")

    def execute_sql(self, query: str) -> pd.DataFrame:
        """Executes a raw SQL statement against DuckDB storage."""
        try:
            return self.conn.execute(query).df()
        except Exception as e:
            raise StorageError(f"SQL execution error [{query}]: {str(e)}")

    def close(self):
        """Cleans up pipeline DuckDB schema and resources."""
        try:
            self.conn.execute(f"DROP SCHEMA IF EXISTS {self.schema_name} CASCADE;")
            log.info(f"Cleaned up DuckDB isolated schema: {self.schema_name}")
        except Exception as e:
            log.warning(f"Failed to drop DuckDB schema {self.schema_name}: {str(e)}")