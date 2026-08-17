# ==============================================================================
# Filepath: core/engine/evaluator.py
# Updated_at: 2026-08-16 17:26:43
# Description: Evaluates dynamic routing conditions and expressions using DuckDB.
# ==============================================================================

from typing import Any, Dict, Optional
from jsonpath_ng.ext import parse

from core.common.exceptions import EvaluatorError
from core.common.logger import log
from core.storage.context import PipelineContext


class VariableEvaluator:
    """Evaluates dynamic parameters and routing conditions directly against Context or DuckDB."""

    @staticmethod
    def evaluate_path(jsonpath_expr: str, context_data: Dict[str, Any]) -> Any:
        """Extracts nested values from a dictionary using JSONPath expression."""
        if not jsonpath_expr:
            return None

        try:
            expr = parse(jsonpath_expr)
            matches = expr.find(context_data)
            if matches and matches[0].value is not None:
                return matches[0].value
            return None
        except Exception as e:
            log.warning(f"[EVALUATOR WARNING] Failed to parse JSONPath [{jsonpath_expr}]: {str(e)}")
            return None

    @staticmethod
    def evaluate_condition(sql_cond: str, context: PipelineContext) -> bool:
        """Evaluates a boolean SQL condition statement against the DuckDB Context."""
        if not sql_cond:
            return True

        try:
            query = f"SELECT ({sql_cond}) AS cond_res;"
            res_df = context.execute_sql(query)
            if res_df is not None and not res_df.empty:
                return bool(res_df.iloc[0]["cond_res"])
            return False
        except Exception as e:
            raise EvaluatorError(f"Failed to evaluate routing SQL condition [{sql_cond}]: {str(e)}")