import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional
import pandas as pd
from core.common.exceptions import DriverError


class NexacroParser:
    """Parses Nexacro XML Dataset responses into Pandas DataFrames."""

    @staticmethod
    def parse_xml_to_dataframe(xml_text: str, dataset_id: Optional[str] = None) -> pd.DataFrame:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            raise DriverError(f"Failed to parse Nexacro XML response: {str(e)}")

        records: List[Dict[str, Any]] = []

        # Locate all Dataset elements
        datasets = root.findall(".//Dataset")
        if not datasets:
            return pd.DataFrame()

        target_ds = datasets[0]
        if dataset_id:
            for ds in datasets:
                if ds.attrib.get("id") == dataset_id:
                    target_ds = ds
                    break

        rows = target_ds.findall(".//Rows/Row")
        for row in rows:
            record: Dict[str, Any] = {}
            for col in row.findall("Col"):
                col_id = col.attrib.get("id")
                if col_id:
                    record[col_id] = col.text or ""
            records.append(record)

        return pd.DataFrame(records)