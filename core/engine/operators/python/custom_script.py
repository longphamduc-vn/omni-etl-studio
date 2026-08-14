from typing import Any, Dict, Callable
from core.engine.operators.base import BaseOperator
from core.engine.operators.registry import OperatorRegistry
from core.storage.context import PipelineContext


@OperatorRegistry.register("python_transform")
class PythonCustomTransformOperator(BaseOperator):
    """Executes arbitrary Python function transformations using Pandas DataFrames."""

    def execute(self, table_name: str, params: Dict[str, Any], context: PipelineContext) -> str:
        transform_func: Callable = params.get("function")
        
        if not transform_func or not callable(transform_func):
            raise ValueError("PythonCustomTransformOperator requires a callable 'function' in params.")

        # Extract DataFrame from DuckDB
        df = context.get_dataframe(table_name)

        # Apply custom Python function
        transformed_df = transform_func(df)

        # Save back to DuckDB table
        context.save_dataframe(table_name, transformed_df)
        return table_name