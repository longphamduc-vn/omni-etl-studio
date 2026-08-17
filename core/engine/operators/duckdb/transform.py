# ==============================================================================
# Filepath: core/engine/operators/duckdb/transform.py
# Updated_at: 2026-08-16 17:30:00
# Description: Universal SQL transformation operator replacing legacy fragmented ops.
# ==============================================================================

from typing import Any, Dict
from jinja2 import Template

from core.common.logger import log
from core.engine.operators.base import BaseOperator
from core.engine.operators.registry import OperatorRegistry
from core.storage.context import PipelineContext


@OperatorRegistry.register("sql_transform")
class SqlTransformOperator(BaseOperator):
    """Executes arbitrary DuckDB SQL statements rendered with Jinja2 context templates."""

    def execute(self, table_name: str, params: Dict[str, Any], context: PipelineContext) -> str:
        full_table = f"{context.schema_name}.{table_name}" if getattr(context, "schema_name", None) else table_name
        raw_query = params.get("query", "SELECT * FROM {{ active_table }}")

        # 1. Prepare Jinja2 evaluation context
        render_scope = {
            "active_table": full_table,
            "inputs": getattr(context, "input_data", {}),
            "session": getattr(context, "session", {}),
            "schema": getattr(context, "schema_name", ""),
        }

        # Render step inputs into template scope if available (DAG Multi-input support)
        if hasattr(context, "get_dataframe"):
            render_scope["tables"] = lambda tid: f"{context.schema_name}.{tid}"

        # 2. Render Jinja2 SQL query
        try:
            rendered_sql = Template(raw_query).render(**render_scope)
        except Exception as e:
            log.error(f"[SQL RENDER ERROR] Failed to render Jinja2 query: {str(e)}")
            raise

        # 3. Wrap in DDL CREATE OR REPLACE TABLE execution
        exec_sql = f"CREATE OR REPLACE TABLE {full_table} AS {rendered_sql};"
        log.info(f"[SQL EXECUTE] {exec_sql}")
        
        context.execute_sql(exec_sql)
        return table_name