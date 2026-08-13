from abc import ABC, abstractmethod
from typing import Any, Dict
from core.storage.context import PipelineContext

class BaseOperator(ABC):
    """Abstract Base Class for all DuckDB and Python Data Operators."""

    @abstractmethod
    def execute(self, table_name: str, params: Dict[str, Any], context: PipelineContext) -> str:
        """Executes transformation on a table inside PipelineContext.
        
        Returns the resulting table name.
        """
        pass