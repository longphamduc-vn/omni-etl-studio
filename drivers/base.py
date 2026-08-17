# ==============================================================================
# Filepath: drivers/base.py
# Updated_at: 2026-08-16 17:38:52
# Description: Abstract base class for protocol drivers and registry lookup.
# ==============================================================================

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type
import pandas as pd

from core.common.logger import log


class BaseDriver(ABC):
    """Abstract protocol driver handling payload creation, transport, and response inspection."""

    @abstractmethod
    def execute(
        self,
        endpoint: str,
        variables: Dict[str, Any],
        error_cfg: Optional[Dict[str, Any]] = None,
        method: str = "POST"
    ) -> pd.DataFrame:
        """Executes API request and returns result converted to Pandas DataFrame."""
        pass

    @abstractmethod
    def inspect_response(
        self,
        payload: Dict[str, Any],
        error_cfg: Optional[Dict[str, Any]]
    ) -> None:
        """Inspects protocol payload for business errors and raises BusinessError if detected."""
        pass


class DriverRegistry:
    """Central registry mapping protocol driver names to concrete driver classes."""

    _drivers: Dict[str, Type[BaseDriver]] = {}

    @classmethod
    def register(cls, name: str):
        """Decorator to register a protocol driver class."""
        def decorator(driver_cls: Type[BaseDriver]):
            cls._drivers[name] = driver_cls
            return driver_cls
        return decorator

    @classmethod
    def get(cls, name: str) -> Type[BaseDriver]:
        """Retrieves a registered driver class by name."""
        if name not in cls._drivers:
            log.error(f"[DRIVER REGISTRY] Driver '{name}' is not registered.")
            raise KeyError(f"Driver '{name}' not found in registry.")
        return cls._drivers[name]