import xml.etree.ElementTree as ET
from typing import Any, Dict, Optional
import pandas as pd
from core.common.exceptions import DriverError


class NexacroBuilder:
    """Builds Nexacro Platform XML request bodies and headers."""

    @staticmethod
    def build_xml_payload(variables: Dict[str, Any], payload_df: Optional[pd.DataFrame] = None, dataset_id: str = "ds_input") -> str:
        try:
            root = ET.Element("Root")

            # 1. Add Parameters block
            params_elem = ET.SubElement(root, "Parameters")
            for var_key, var_val in variables.items():
                param = ET.SubElement(params_elem, "Parameter", id=var_key)
                param.text = str(var_val) if var_val is not None else ""

            # 2. Add Dataset block if DataFrame payload is provided
            if payload_df is not None and not payload_df.empty:
                ds_elem = ET.SubElement(root, "Dataset", id=dataset_id)

                # Column Information header
                colinfo_elem = ET.SubElement(ds_elem, "ColumnInfo")
                for col_name in payload_df.columns:
                    # Infer basic XML data type
                    col_type = "STRING"
                    if pd.api.types.is_integer_dtype(payload_df[col_name]):
                        col_type = "INT"
                    elif pd.api.types.is_float_dtype(payload_df[col_name]):
                        col_type = "FLOAT"

                    ET.SubElement(colinfo_elem, "Const" if False else "Column", id=col_name, type=col_type, size="256")

                # Rows data
                rows_elem = ET.SubElement(ds_elem, "Rows")
                for _, row in payload_df.iterrows():
                    row_elem = ET.SubElement(rows_elem, "Row")
                    for col_name in payload_df.columns:
                        col_val = row[col_name]
                        col_elem = ET.SubElement(row_elem, "Col", id=col_name)
                        col_elem.text = str(col_val) if pd.notna(col_val) else ""

            return ET.tostring(root, encoding="utf-8", method="xml").decode("utf-8")

        except Exception as e:
            raise DriverError(f"Failed to build Nexacro XML request: {str(e)}")