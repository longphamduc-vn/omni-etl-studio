from typing import Dict, Type
from core.engine.operators.base import BaseOperator
from core.common.exceptions import TransformationError

class OperatorRegistry:
    """Central registry mapping operator identifiers to concrete operator instances."""
    _registry: Dict[str, Type[BaseOperator]] = {}

    @classmethod
    def register(cls, name: str):
        def decorator(operator_cls: Type[BaseOperator]):
            cls._registry[name.lower()] = operator_cls
            return operator_cls
        return decorator

    @classmethod
    def get(cls, name: str) -> BaseOperator:
        operator_cls = cls._registry.get(name.lower())
        if not operator_cls:
            raise TransformationError(f"Operator '{name}' is not registered.")
        return operator_cls()