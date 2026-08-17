# Filepath: drivers/nexacro.py
# Updated_at: 2026-08-17 07:05:00
# Description: Enhanced Nexacro Driver with comprehensive Logging for payloads and responses.

from typing import Any, Dict, Optional
import xml.etree.ElementTree as ET
import pandas as pd
import requests

from core.common.exceptions import BusinessError, DriverError
from core.common.logger import log
from drivers.base import BaseDriver, DriverRegistry


@DriverRegistry.register("nexacro")
class NexacroDriver(BaseDriver):
    """Driver handling Nexacro XML protocol serialization and dynamic HTTP transport with active logging."""

    def execute(
        self,
        endpoint: str,
        variables: Dict[str, Any],
        error_cfg: Optional[Dict[str, Any]] = None,
        method: str = "POST"
    ) -> pd.DataFrame:
        """Constructs Nexacro XML payload, executes HTTP POST, and extracts Datasets with explicit logs."""
        log.info(f"[NEXACRO REQUEST] Invoking endpoint: {endpoint}")

        params = variables.get("parameters", {})
        datasets = variables.get("datasets", {})
        
        req_headers = variables.get("headers", {})
        if not isinstance(req_headers, dict):
            req_headers = {}

        if "Content-Type" not in req_headers:
            req_headers["Content-Type"] = "application/xml; charset=UTF-8"

        # Log Headers gửi đi (Đã ẩn bớt thông tin nhạy cảm nếu cần)
        log.info(f"[NEXACRO HEADERS] {req_headers}")

        xml_payload = self._build_xml_payload(params, datasets)
        
        # 🎯 Đổi sang log.info để luôn hiển thị Payload XML
        log.info(f"[NEXACRO PAYLOAD OUTGOING]\n{xml_payload}")

        try:
            resp = requests.post(
                endpoint,
                data=xml_payload.encode("utf-8"),
                headers=req_headers,
                timeout=30
            )
            log.info(f"[NEXACRO HTTP STATUS] {resp.status_code}")
            log.info(f"[NEXACRO RAW RESPONSE BODY]\n{resp.text}")

            if resp.status_code != 200:
                raise DriverError(f"HTTP Error {resp.status_code}: {resp.text}")
        except Exception as e:
            log.error(f"[NEXACRO TRANSPORT ERROR] {str(e)}")
            raise DriverError(f"Nexacro transport failure: {str(e)}")

        try:
            parsed_data = self._parse_xml_response(resp.text)
            log.info(f"[NEXACRO PARSED DATA] Parameters: {parsed_data.get('parameters')} | Datasets: {list(parsed_data.get('datasets', {}).keys())}")
        except Exception as e:
            log.error(f"[NEXACRO PARSE ERROR] Raw text failed to parse: {resp.text}")
            raise DriverError(f"Nexacro XML response parse error: {str(e)}")

        # Inspect Business Errors (ErrorCode / ErrorMsg)
        self.inspect_response(parsed_data, error_cfg)

        # Return primary output Dataset as DataFrame
        out_datasets = parsed_data.get("datasets", {})
        if out_datasets:
            first_ds_key = list(out_datasets.keys())[0]
            df_res = pd.DataFrame(out_datasets[first_ds_key])
            log.info(f"[NEXACRO OUTPUT DATAFRAME] Dataset '{first_ds_key}' with {len(df_res)} rows.")
            return df_res

        log.warning("[NEXACRO OUTPUT DATASET] No output datasets extracted from response XML.")
        return pd.DataFrame()

    def inspect_response(self, payload: Dict[str, Any], error_cfg: Optional[Dict[str, Any]]) -> None:
        """Inspects Nexacro ErrorCode and ErrorMsg parameter fields dynamically."""
        if not error_cfg:
            error_cfg = {}

        code_key = error_cfg.get("code_field", "ErrorCode")
        msg_key = error_cfg.get("msg_field", "ErrorMsg")
        success_val = error_cfg.get("success_value", 0)

        params = payload.get("parameters", {})
        raw_code = params.get(code_key, 0)
        err_msg = params.get(msg_key, "Unknown Nexacro error")

        try:
            err_code = int(raw_code)
        except (ValueError, TypeError):
            err_code = -1

        if err_code != success_val:
            log.error(f"[NEXACRO BUSINESS ERROR] Code: {err_code}, Message: {err_msg}")
            raise BusinessError(code=err_code, msg=err_msg, payload=payload)

    def _build_xml_payload(self, params: Dict[str, Any], datasets: Dict[str, Any]) -> str:
        root = ET.Element("Root", xmlns="http://www.nexacroplatform.com/platform/dataset")
        p_elem = ET.SubElement(root, "Parameters")

        if isinstance(params, dict):
            for k, v in params.items():
                param = ET.SubElement(p_elem, "Parameter", id=str(k))
                param.text = str(v) if v is not None else ""

        if isinstance(datasets, dict):
            for ds_id, rows in datasets.items():
                ds_elem = ET.SubElement(root, "Dataset", id=ds_id)
                if rows and isinstance(rows, list):
                    cols = list(rows[0].keys())
                    col_info = ET.SubElement(ds_elem, "ColumnInfo")
                    for c in cols:
                        ET.SubElement(col_info, "Column", id=str(c), type="STRING", size="256")

                    rows_elem = ET.SubElement(ds_elem, "Rows")
                    for r in rows:
                        row_elem = ET.SubElement(rows_elem, "Row")
                        for c in cols:
                            col_val = ET.SubElement(row_elem, "Col", id=str(c))
                            col_val.text = str(r.get(c, "")) if r.get(c) is not None else ""

        return ET.tostring(root, encoding="unicode")

    def _parse_xml_response(self, xml_str: str) -> Dict[str, Any]:
        root = ET.fromstring(xml_str)
        extracted_params = {}
        extracted_datasets = {}

        # Parse Parameters
        for p in root.findall(".//Parameter"):
            pid = p.attrib.get("id")
            if pid:
                extracted_params[pid] = p.text or ""

        # Parse Datasets
        for ds in root.findall(".//Dataset"):
            ds_id = ds.attrib.get("id", "ds_out")
            rows_data = []
            cols = [c.attrib.get("id") for c in ds.findall(".//ColumnInfo/Column")]

            for row in ds.findall(".//Rows/Row"):
                row_dict = {}
                for col in row.findall("Col"):
                    cid = col.attrib.get("id")
                    if cid in cols or not cols:
                        row_dict[cid] = col.text or ""
                rows_data.append(row_dict)

            extracted_datasets[ds_id] = rows_data

        return {"parameters": extracted_params, "datasets": extracted_datasets}