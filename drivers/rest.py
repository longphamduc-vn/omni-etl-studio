# ==============================================================================
# Filepath: drivers/rest.py
# Updated_at: 2026-08-16 17:38:52
# Description: Standard REST API driver with dynamic JSON error inspection.
# ==============================================================================

from typing import Any, Dict, Optional
import pandas as pd
import requests

from core.common.exceptions import BusinessError, DriverError
from core.common.logger import log
from drivers.base import BaseDriver, DriverRegistry


@DriverRegistry.register("rest")
class RestDriver(BaseDriver):
    """Driver handling standard REST JSON endpoints and JSON error inspection."""

    def execute(
        self,
        endpoint: str,
        variables: Dict[str, Any],
        error_cfg: Optional[Dict[str, Any]] = None,
        method: str = "POST"
    ) -> pd.DataFrame:
        """Executes HTTP REST request and returns response payload converted to DataFrame."""
        log.info(f"[REST REQUEST] [{method}] {endpoint}")

        params = variables.get("parameters", {})
        datasets = variables.get("datasets", {})

        payload = {**params, **datasets}
        headers = {"Content-Type": "application/json"}

        try:
            if method.upper() == "GET":
                resp = requests.get(endpoint, params=params, headers=headers, timeout=30)
            else:
                resp = requests.post(endpoint, json=payload, headers=headers, timeout=30)

            if resp.status_code not in [200, 201]:
                raise DriverError(f"HTTP Error {resp.status_code}: {resp.text}")

            json_resp = resp.json()
        except Exception as e:
            raise DriverError(f"REST invocation failure: {str(e)}")

        # Inspect Business Errors
        self.inspect_response(json_resp, error_cfg)

        # Normalize JSON response to DataFrame
        if isinstance(json_resp, list):
            return pd.DataFrame(json_resp)
        elif isinstance(json_resp, dict):
            for k in ["data", "items", "results", "records"]:
                if k in json_resp and isinstance(json_resp[k], list):
                    return pd.DataFrame(json_resp[k])
            return pd.DataFrame([json_resp])

        return pd.DataFrame()

    def inspect_response(self, payload: Dict[str, Any], error_cfg: Optional[Dict[str, Any]]) -> None:
        """Inspects generic REST JSON response structure for business-level errors."""
        if not error_cfg or not isinstance(payload, dict):
            return

        code_key = error_cfg.get("code_field", "code")
        msg_key = error_cfg.get("msg_field", "message")
        success_val = error_cfg.get("success_value", 200)

        if code_key in payload:
            err_code = payload.get(code_key)
            err_msg = payload.get(msg_key, "Unknown REST API error")

            if err_code != success_val:
                log.error(f"[REST BUSINESS ERROR] Code: {err_code}, Message: {err_msg}")
                raise BusinessError(code=err_code, msg=err_msg, payload=payload)