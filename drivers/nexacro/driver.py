import requests
import pandas as pd
from typing import Any, Dict

from config.settings import settings
from core.common.exceptions import DriverError
# FIX: Import trực tiếp từ drivers.base để tránh Circular Import
from drivers.base import BaseDriver, DriverRegistry
from drivers.nexacro.builder import NexacroBuilder
from drivers.nexacro.cleaner import NexacroCleaner
from drivers.nexacro.parser import NexacroParser


@DriverRegistry.register("nexacro")
class NexacroDriver(BaseDriver):
    """Protocol driver interacting with Nexacro Platform API endpoints via XML payloads."""

    def execute(self, endpoint: str, variables: Dict[str, Any], method: str = "POST") -> pd.DataFrame:
        try:
            xml_payload = NexacroBuilder.build_xml_payload(variables=variables)
            headers = {"Content-Type": "application/xml; charset=utf-8"}
            
            http_method = method.upper()
            if http_method == "GET":
                response = requests.get(
                    endpoint, 
                    params=variables, 
                    headers=headers, 
                    timeout=settings.DEFAULT_HTTP_TIMEOUT
                )
            else:
                response = requests.request(
                    method=http_method,
                    url=endpoint, 
                    data=xml_payload.encode("utf-8"), 
                    headers=headers, 
                    timeout=settings.DEFAULT_HTTP_TIMEOUT
                )
                
            response.raise_for_status()

            cleaned_xml = NexacroCleaner.clean_xml(response.text)
            return NexacroParser.parse_xml_to_dataframe(cleaned_xml)
            
        except requests.RequestException as re_err:
            raise DriverError(f"Nexacro HTTP transport failure [{endpoint}]: {str(re_err)}")
        except Exception as e:
            raise DriverError(f"Nexacro driver execution error: {str(e)}")