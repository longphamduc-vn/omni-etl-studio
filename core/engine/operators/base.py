# ==============================================================================
# Filepath: core/engine/operators/base.py
# Updated_at: 2026-08-16 17:36:00
# Description: Abstract base class for all data transformation operators.
# ==============================================================================

from abc import ABC, abstractmethod
from typing import Any, Dict
from core.storage.context import PipelineContext


class BaseOperator(ABC):
    """Abstract base class for data transformation operators executing against PipelineContext."""

    @abstractmethod
    def execute(self, table_name: str, params: Dict[str, Any], context: PipelineContext) -> str:
        """Executes transformation on target table and returns output table name.

        Args:
            table_name (str): Active input table name in DuckDB context.
            params (Dict[str, Any]): Operator execution parameters.
            context (PipelineContext): Execution pipeline storage context.

        Returns:
            str: Output table name after applying the transformation operator.
        """
        pass