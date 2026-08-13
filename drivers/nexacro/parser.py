import xml.etree.ElementTree as ET
from typing import Optional
import pandas as pd
from core.common.exceptions import DriverError
from core.common.logger import log


class NexacroParser:
    """Parses Nexacro XML responses into Pandas DataFrames."""

    @staticmethod
    def parse_xml_to_dataframe(xml_text: str, dataset_id: Optional[str] = None) -> pd.DataFrame:
        try:
            root = ET.fromstring(xml_text)

            # Locate Dataset tag
            target_ds = None
            datasets = root.findall(".//Dataset")

            if not datasets:
                log.warning("No <Dataset> tag found in Nexacro XML response.")
                return pd.DataFrame()

            if dataset_id:
                for ds in datasets:
                    if ds.get("id") == dataset_id:
                        target_ds = ds
                        break
                if target_ds is None:
                    log.warning(f"Target dataset id '{dataset_id}' not found. Defaulting to first dataset.")
                    target_ds = datasets[0]
            else:
                target_ds = datasets[0]

            # Parse column definitions
            col_names = []
            for col in target_ds.findall("./ColumnInfo/Column"):
                col_id = col.get("id")
                if col_id:
                    col_names.append(col_id)

            # Extract Rows
            records = []
            for row in target_ds.findall("./Rows/Row"):
                row_data = {}
                for col in row.findall("Col"):
                    cid = col.get("id")
                    row_data[cid] = col.text if col.text is not None else ""
                records.append(row_data)

            df = pd.DataFrame(records)

            # Ensure all defined columns exist even if rows were empty
            for col in col_names:
                if col not in df.columns:
                    df[col] = None

            return df if not df.empty else pd.DataFrame(columns=col_names)

        except ET.ParseError as pe:
            raise DriverError(f"XML syntax parse error in Nexacro response: {str(pe)}")
        except Exception as e:
            raise DriverError(f"Failed to parse Nexacro XML response: {str(e)}")