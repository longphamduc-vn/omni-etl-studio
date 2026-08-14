from typing import List  # <--- Bổ sung dòng này để định nghĩa kiểu List
from core.common.logger import log
from core.common.schemas import TransformRule
from core.engine.operators.registry import OperatorRegistry
from core.storage.context import PipelineContext

# Import all operator modules to register decorators automatically
import core.engine.operators.duckdb.aggregate
import core.engine.operators.duckdb.cleaning
import core.engine.operators.duckdb.enrichment
import core.engine.operators.duckdb.join
import core.engine.operators.duckdb.reshape
import core.engine.operators.python.custom_script


class DataTransformer:
    """Dispatches and executes sequential data transformation operators against PipelineContext."""

    @staticmethod
    def transform(table_name: str, rules: List[TransformRule], context: PipelineContext) -> str:
        if not rules:
            return table_name

        current_table = table_name

        for rule in rules:
            log.info(f"Applying transformation operator [{rule.operator}] on table '{current_table}'")
            operator_inst = OperatorRegistry.get(rule.operator)
            current_table = operator_inst.execute(
                table_name=current_table,
                params=rule.params,
                context=context
            )

        return current_table