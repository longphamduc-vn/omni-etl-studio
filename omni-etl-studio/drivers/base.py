from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import pandas as pd


class BaseDriver(ABC):
    """Abstract Protocol Driver Interface enforcing unified behavior for request building,
    payload cleaning, response parsing, and execution.
    """

    @abstractmethod
    def build_request(self, endpoint: str, variables: Dict[str, Any], payload_df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Builds protocol-specific request parameters, headers, and body payload.

        Returns a dictionary containing execution details e.g.,
        {'url': ..., 'headers': ..., 'body': ...}
        """
        pass

    @abstractmethod
    def clean_payload(self, raw_response_text: str) -> str:
        """Cleans raw response content (e.g., stripping XML namespaces, fixing encoding artifacts, sanitizing)."""
        pass

    @abstractmethod
    def parse_response(self, cleaned_response_text: str, dataset_id: Optional[str] = None) -> pd.DataFrame:
        """Parses cleaned response payload into a standardized Pandas DataFrame."""
        pass

    @abstractmethod
    def execute(self, endpoint: str, variables: Dict[str, Any], payload_df: Optional[pd.DataFrame] = None, dataset_id: Optional[str] = None) -> pd.DataFrame:
        """Executes full request pipeline: build -> network transport -> clean -> parse."""
        pass