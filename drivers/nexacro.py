import xml.etree.ElementTree as ET
from typing import Any, Dict
import pandas as pd
import requests
from core.common.logger import log
from drivers.base import BaseDriver, DriverRegistry


@DriverRegistry.register("nexacro")
class NexacroDriver(BaseDriver):
    """Packs resolved variables into Nexacro XML Payload, sends HTTP request, and parses multi-dataset XML Responses."""

    @staticmethod
    def build_xml_payload(resolved_vars: Dict[str, Any]) -> str:
        root = ET.Element("Root", {"xmlns": "http://tobesoft.com"})
        
        # 1. Build Parameters
        params = resolved_vars.get("parameters", {})
        if params:
            params_node = ET.SubElement(root, "Parameters")
            for param_id, val in params.items():
                p_node = ET.SubElement(params_node, "Parameter", {"id": param_id})
                p_node.text = "" if val is None else str(val)

        # 2. Build Datasets
        datasets = resolved_vars.get("datasets", {})
        for ds_id, rows in datasets.items():
            ds_node = ET.SubElement(root, "Dataset", {"id": ds_id})
            
            if rows and isinstance(rows, list) and len(rows) > 0:
                col_info_node = ET.SubElement(ds_node, "ColumnInfo")
                sample_row = rows[0]
                for col_name in sample_row.keys():
                    ET.SubElement(col_info_node, "Column", {
                        "id": col_name,
                        "type": "STRING",
                        "size": "256"
                    })
                
                rows_node = ET.SubElement(ds_node, "Rows")
                for row_data in rows:
                    row_node = ET.SubElement(rows_node, "Row")
                    for col_id, col_val in row_data.items():
                        col_node = ET.SubElement(row_node, "Col", {"id": col_id})
                        col_node.text = "" if col_val is None else str(col_val)

        return '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding="utf-8").decode("utf-8")

    @staticmethod
    def parse_xml_response(xml_string: str) -> pd.DataFrame:
        if not xml_string or not xml_string.strip():
            return pd.DataFrame()

        try:
            root = ET.fromstring(xml_string)
        except Exception as e:
            log.error(f"Failed to parse Nexacro XML response: {str(e)}")
            return pd.DataFrame()

        parsed_datasets: Dict[str, pd.DataFrame] = {}

        for ds_node in root.findall("Dataset"):
            ds_id = ds_node.get("id", "ds_default")
            rows_data = []

            rows_node = ds_node.find("Rows")
            if rows_node is not None:
                for row_node in rows_node.findall("Row"):
                    row_dict = {}
                    for col_node in row_node.findall("Col"):
                        col_id = col_node.get("id")
                        if col_id:
                            row_dict[col_id] = col_node.text
                    rows_data.append(row_dict)

            parsed_datasets[ds_id] = pd.DataFrame(rows_data)

        if not parsed_datasets:
            return pd.DataFrame()

        if len(parsed_datasets) == 1:
            return list(parsed_datasets.values())[0]

        # Merge đa Dataset (ds_master, ds_inventory, ds_pricing)
        merged_df = None
        for ds_id, df in parsed_datasets.items():
            if df.empty:
                continue
            if merged_df is None:
                merged_df = df
            else:
                join_keys = [col for col in ["product_id", "id"] if col in merged_df.columns and col in df.columns]
                if join_keys:
                    merged_df = pd.merge(merged_df, df, on=join_keys, how="outer", suffixes=("", f"_{ds_id}"))
                else:
                    merged_df = pd.concat([merged_df, df], axis=1)

        return merged_df if merged_df is not None else pd.DataFrame()

    def execute(self, endpoint: str, variables: Dict[str, Any], method: str = "POST") -> pd.DataFrame:
        xml_payload = self.build_xml_payload(variables)
        headers = {
            "Content-Type": "application/xml",
            "Accept": "application/xml"
        }

        try:
            response = requests.request(
                method=method,
                url=endpoint,
                data=xml_payload.encode("utf-8"),
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            return self.parse_xml_response(response.text)
        except Exception as e:
            log.error(f"Error executing Nexacro HTTP request to [{endpoint}]: {str(e)}")
            return pd.DataFrame()