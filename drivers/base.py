from abc import ABC, abstractmethod
from typing import Any, Dict, Type
import pandas as pd
from core.common.exceptions import DriverError


class BaseDriver(ABC):
    """Abstract Base Class for all protocol drivers (e.g., Nexacro, REST, SQL)."""

    @abstractmethod
    def execute(self, endpoint: str, variables: Dict[str, Any]) -> pd.DataFrame:
        """Executes a protocol request and returns the resulting dataset as a Pandas DataFrame."""
        pass


class DriverRegistry:
    """Central registry managing protocol driver instances."""

    _registry: Dict[str, Type[BaseDriver]] = {}

    @classmethod
    def register(cls, name: str):
        """Decorator to register a concrete BaseDriver subclass."""
        def decorator(subclass: Type[BaseDriver]):
            cls._registry[name.lower()] = subclass
            return subclass
        return decorator

    @classmethod
    def get(cls, name: str) -> Type[BaseDriver]:
        """Retrieves a registered driver class by protocol name."""
        driver_name = name.lower()
        if driver_name not in cls._registry:
            raise DriverError(f"Driver protocol '{name}' is not registered. Available: {list(cls._registry.keys())}")
        return cls._registry[driver_name]


@DriverRegistry.register("passthrough")
@DriverRegistry.register("none")
class PassthroughDriver(BaseDriver):
    """Fallback driver for pure transformation steps requiring no network/API calls."""

    def execute(self, endpoint: str, variables: Dict[str, Any]) -> pd.DataFrame:
        return pd.DataFrame()



class BaseDriver(ABC):
    """Abstract Base Class for all protocol drivers (e.g., Nexacro, REST, SQL)."""

    @abstractmethod
    def execute(self, endpoint: str, variables: Dict[str, Any], method: str = "POST") -> pd.DataFrame:
        """Executes a protocol request and returns the resulting dataset as a Pandas DataFrame."""
        pass


@DriverRegistry.register("passthrough")
@DriverRegistry.register("none")
class PassthroughDriver(BaseDriver):
    """Fallback driver for pure transformation steps requiring no network/API calls."""

    def execute(self, endpoint: str, variables: Dict[str, Any], method: str = "POST") -> pd.DataFrame:
        return pd.DataFrame()