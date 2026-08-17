# ==============================================================================
# Filepath: core/engine/operators/registry.py
# Updated_at: 2026-08-16 17:36:00
# Description: Central operator registry managing instantiation and lookup.
# ==============================================================================

from typing import Dict, Type
from core.common.logger import log
from core.engine.operators.base import BaseOperator


class OperatorRegistry:
    """Central registry mapping operator names to concrete BaseOperator classes."""

    _operators: Dict[str, Type[BaseOperator]] = {}

    @classmethod
    def register(cls, name: str):
        """Decorator registering a transformation operator class.

        Args:
            name (str): Unique operator registration identifier.
        """
        def decorator(op_cls: Type[BaseOperator]):
            if name in cls._operators:
                log.warning(f"[OPERATOR REGISTRY] Overwriting existing operator registration '{name}'.")
            cls._operators[name] = op_cls
            return op_cls
        return decorator

    @classmethod
    def get(cls, name: str) -> BaseOperator:
        """Instantiates and returns a registered operator instance by name.

        Args:
            name (str): Registered operator identifier.

        Returns:
            BaseOperator: Instantiated operator instance.

        Raises:
            KeyError: If operator name is not found in registry.
        """
        if name not in cls._operators:
            log.error(f"[OPERATOR REGISTRY] Operator '{name}' is not registered.")
            raise KeyError(f"Operator '{name}' not found in registry.")
        
        return cls._operators[name]()

    @classmethod
    def list_operators(cls) -> Dict[str, Type[BaseOperator]]:
        """Returns dictionary of all currently registered operator classes."""
        return cls._operators.copy()