from typing import List
from core.common.schemas import TransformRule
from core.engine.operators.registry import OperatorRegistry
from core.storage.context import PipelineContext
from core.common.logger import log

# Import package operators để kích hoạt các decorator @OperatorRegistry.register(...)
import core.engine.operators  # noqa: F401


class DataTransformer:
    """Dispatcher engine that coordinates data transformation pipeline rules."""

    @staticmethod
    def transform(table_name: str, rules: List[TransformRule], context: PipelineContext) -> str:
        """Applies a list of transformation rules sequentially over DuckDB tables."""
        if not rules:
            return table_name

        current_table = table_name

        for rule in rules:
            log.debug(f"Executing operator [{rule.operator}] on table [{current_table}]")
            operator_instance = OperatorRegistry.get(rule.operator)
            current_table = operator_instance.execute(current_table, rule.params, context)

        return current_table