# ==============================================================================
# Filepath: core/engine/operators/python/custom_script.py
# Updated_at: 2026-08-16 17:35:00
# Description: Fallback operator executing custom Python transformation functions.
# ==============================================================================

from typing import Any, Dict
import pandas as pd

from core.common.logger import log
from core.engine.operators.base import BaseOperator
from core.engine.operators.registry import OperatorRegistry
from core.storage.context import PipelineContext


@OperatorRegistry.register("python_script")
class PythonScriptOperator(BaseOperator):
    """Executes dynamic Python script code against DuckDB table DataFrames."""

    def execute(self, table_name: str, params: Dict[str, Any], context: PipelineContext) -> str:
        script_code = params.get("script", "")
        function_name = params.get("function", "transform_data")
        full_table = f"{context.schema_name}.{table_name}" if getattr(context, "schema_name", None) else table_name

        if not script_code:
            log.warning(f"[PYTHON SCRIPT] No script code provided for table '{table_name}'. Skipping.")
            return table_name

        # 1. Fetch current table as Pandas DataFrame from DuckDB
        df = context.get_dataframe(table_name)
        if df is None:
            df = pd.DataFrame()

        # 2. Prepare dynamic execution namespace scope
        local_scope: Dict[str, Any] = {}
        global_scope: Dict[str, Any] = {
            "pd": pd,
            "inputs": getattr(context, "input_data", {}),
            "session": getattr(context, "session", {}),
            "log": log,
        }

        try:
            # 3. Compile and execute user-defined Python script string
            exec(script_code, global_scope, local_scope)

            if function_name in local_scope and callable(local_scope[function_name]):
                transform_func = local_scope[function_name]
                log.info(f"[PYTHON SCRIPT EXECUTE] Invoking function '{function_name}'")
                res_df = transform_func(df, context)
            else:
                log.warning(f"[PYTHON SCRIPT WARNING] Function '{function_name}' not found in script.")
                res_df = df

            # 4. Save transformed DataFrame back to DuckDB Context
            if isinstance(res_df, pd.DataFrame):
                context.save_dataframe(table_name, res_df)
            else:
                log.error(f"[PYTHON SCRIPT ERROR] Script output is not a Pandas DataFrame.")

        except Exception as e:
            log.error(f"[PYTHON SCRIPT FAILURE] Error executing script on table '{table_name}': {str(e)}")
            raise

        return table_name