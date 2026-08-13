from core.engine.operators.base import BaseOperator
from core.engine.operators.registry import OperatorRegistry

# Import concrete operators so decorators run upon module initialization
from core.engine.operators.duckdb import aggregate, cleaning, reshape

__all__ = ["BaseOperator", "OperatorRegistry"]