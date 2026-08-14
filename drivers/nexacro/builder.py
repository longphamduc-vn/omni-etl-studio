import json
import xml.etree.ElementTree as ET
from typing import Any, Dict, List
from core.common.exceptions import DriverError


class NexacroBuilder:
    """Constructs XML payload and JSON representation formatted for Nexacro Platform Protocol."""

    @classmethod
    def _is_dataset_type(cls, key: str, val: Any) -> bool:
        """Determines if a variable should be classified as a Dataset."""
        if isinstance(val, list):
            return True
        if isinstance(val, dict) and key.startswith("ds_"):
            return True
        if key.startswith("ds_") or key.endswith("_list") or key.endswith("_table"):
            return True
        if isinstance(val, str) and val.strip().startswith("[") and val.strip().endswith("]"):
            try:
                parsed = json.loads(val)
                return isinstance(parsed, list)
            except Exception:
                return False
        return False

    @classmethod
    def prepare_structured_payload(cls, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Separates variables explicitly into parameters (scalars) and datasets (tables/lists)."""
        parameters: Dict[str, Any] = {}
        datasets: Dict[str, List[Dict[str, Any]]] = {}

        for key, val in variables.items():
            if val is None:
                continue

            # Parse stringified JSON arrays if necessary
            if isinstance(val, str) and val.strip().startswith("[") and val.strip().endswith("]"):
                try:
                    val = json.loads(val)
                except Exception:
                    pass

            # 1. CLASSIFY AS DATASET
            if cls._is_dataset_type(key, val):
                ds_rows = []
                if isinstance(val, list):
                    ds_rows = [row for row in val if isinstance(row, dict)]
                elif isinstance(val, dict):
                    # FIX: Auto-wrap single record dict (e.g. from $.loop_row or $.session) into a 1-row Dataset list
                    ds_rows = [val]

                ds_key = key if key.startswith("ds_") else f"ds_{key}"
                datasets[ds_key] = ds_rows

            # 2. CLASSIFY AS PARAMETER
            else:
                parameters[key] = str(val)

        return {
            "parameters": parameters,
            "datasets": datasets
        }

    @classmethod
    def build_xml_payload(cls, variables: Dict[str, Any]) -> str:
        """Builds official Nexacro XML Payload matching Root > Parameters & Datasets structure."""
        try:
            root = ET.Element("Root", xmlns="http://www.nexacro.com")
            structured = cls.prepare_structured_payload(variables)

            # 1. Build <Parameters> wrapper and <Parameter> items
            params_dict = structured["parameters"]
            if params_dict:
                params_elem = ET.SubElement(root, "Parameters")
                for param_id, param_val in params_dict.items():
                    param = ET.SubElement(params_elem, "Parameter", id=str(param_id))
                    param.text = str(param_val)

            # 2. Build <Dataset> items
            for ds_id, rows in structured["datasets"].items():
                ds = ET.SubElement(root, "Dataset", id=str(ds_id))
                col_info = ET.SubElement(ds, "ColumnInfo")

                if rows:
                    first_row = rows[0]
                    for col_name in first_row.keys():
                        ET.SubElement(col_info, "Column", id=str(col_name), type="STRING", size="255")

                    rows_elem = ET.SubElement(ds, "Rows")
                    for item in rows:
                        row_elem = ET.SubElement(rows_elem, "Row")
                        for col_name, col_val in item.items():
                            col_elem = ET.SubElement(row_elem, "Col", id=str(col_name))
                            col_elem.text = str(col_val) if col_val is not None else ""
                else:
                    ET.SubElement(ds, "Rows")

            return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")

        except Exception as e:
            raise DriverError(f"Failed to build Nexacro XML payload: {str(e)}")