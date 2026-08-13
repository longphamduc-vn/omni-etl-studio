from typing import Any, Dict, Optional
import pandas as pd
import requests

from config.settings import settings
from core.common.exceptions import DriverError
from core.common.logger import log
from drivers.base import BaseDriver
from drivers.nexacro.builder import NexacroBuilder
from drivers.nexacro.cleaner import NexacroCleaner
from drivers.nexacro.parser import NexacroParser


class NexacroDriver(BaseDriver):
    """Production protocol driver for Nexacro Platform Web Services."""

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()

    def build_request(self, endpoint: str, variables: Dict[str, Any], payload_df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        xml_body = NexacroBuilder.build_xml_payload(variables, payload_df)
        headers = {
            "Content-Type": "application/xml; charset=UTF-8",
            "User-Agent": f"{settings.PROJECT_NAME}/1.0"
        }
        return {
            "url": endpoint,
            "headers": headers,
            "data": xml_body
        }

    def clean_payload(self, raw_response_text: str) -> str:
        return NexacroCleaner.clean_xml(raw_response_text)

    def parse_response(self, cleaned_response_text: str, dataset_id: Optional[str] = None) -> pd.DataFrame:
        return NexacroParser.parse_xml_to_dataframe(cleaned_response_text, dataset_id=dataset_id)

    def execute(self, endpoint: str, variables: Dict[str, Any], payload_df: Optional[pd.DataFrame] = None, dataset_id: Optional[str] = None) -> pd.DataFrame:
        req_kwargs = self.build_request(endpoint, variables, payload_df)

        try:
            log.debug(f"Dispatching HTTP POST request to Nexacro endpoint: {endpoint}")
            response = self.session.post(
                url=req_kwargs["url"],
                headers=req_kwargs["headers"],
                data=req_kwargs["data"],
                timeout=settings.DEFAULT_HTTP_TIMEOUT
            )
            response.raise_for_status()

            cleaned_xml = self.clean_payload(response.text)
            df_result = self.parse_response(cleaned_xml, dataset_id=dataset_id)

            log.info(f"Successfully executed Nexacro request. Parsed {len(df_result)} records.")
            return df_result

        except requests.RequestException as re:
            raise DriverError(f"HTTP communication error with Nexacro endpoint [{endpoint}]: {str(re)}")
        except Exception as e:
            raise DriverError(f"Nexacro driver execution failure: {str(e)}")


__all__ = ["NexacroDriver", "NexacroBuilder", "NexacroCleaner", "NexacroParser"]