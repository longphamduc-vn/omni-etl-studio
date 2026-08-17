# ==============================================================================
# Filepath: core/engine/transformer.py
# Updated_at: 2026-08-16 17:26:43
# Description: Dispatches sequential DuckDB transformations to registered operators.
# ==============================================================================

from typing import List
from core.common.logger import log
from core.common.schemas import TransformRule
from core.engine.operators.registry import OperatorRegistry
from core.storage.context import PipelineContext

# Import operator package to trigger registry decorators automatically
import core.engine.operators.duckdb
import core.engine.operators.python


class DataTransformer:
    """Dispatches sequential transformation rules across active DuckDB tables."""

    @staticmethod
    def transform(table_name: str, rules: List[TransformRule], context: PipelineContext) -> str:
        """Executes a list of transformation rules against the target table sequentially."""
        if not rules:
            return table_name

        curr_table = table_name

        for rule in rules:
            rule_dict = rule.model_dump() if hasattr(rule, "model_dump") else rule
            op_name = rule_dict.get("operator")
            params = rule_dict.get("params", {})

            log.info(f"[TRANSFORM] Executing operator [{op_name}] on table '{curr_table}'")
            op_inst = OperatorRegistry.get(op_name)
            
            curr_table = op_inst.execute(
                table_name=curr_table,
                params=params,
                context=context
            )

        return curr_table