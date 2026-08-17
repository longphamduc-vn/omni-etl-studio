# ==============================================================================
# Filepath: drivers/excel_ingest.py
# Updated_at: 2026-08-16 17:38:52
# Description: Driver reading and auto-cleaning unstandardized Excel files using DuckDB.
# ==============================================================================

import re
from typing import Any, Dict, Optional
import pandas as pd

from core.common.logger import log
from drivers.base import BaseDriver, DriverRegistry


@DriverRegistry.register("excel_ingest")
class ExcelIngestDriver(BaseDriver):
    """Driver ingesting and standardizing unformatted Excel spreadsheets."""

    def execute(
        self,
        endpoint: str,
        variables: Dict[str, Any],
        error_cfg: Optional[Dict[str, Any]] = None,
        method: str = "POST"
    ) -> pd.DataFrame:
        """Reads Excel file and standardizes headers into clean snake_case format."""
        file_path = endpoint or variables.get("parameters", {}).get("file_path", "")
        log.info(f"[EXCEL INGEST] Loading file: {file_path}")

        try:
            raw_df = pd.read_excel(file_path)
            if raw_df.empty:
                return pd.DataFrame()

            # 1. Clean and standardize column names (Remove Vietnamese accents and special characters)
            clean_cols = [self._clean_header(str(col)) for col in raw_df.columns]
            raw_df.columns = clean_cols

            # 2. Trim string values across dataframe
            for col in raw_df.select_dtypes(include=["object", "string"]).columns:
                raw_df[col] = raw_df[col].astype(str).str.strip()

            # 3. Drop completely empty rows
            clean_df = raw_df.dropna(how="all")
            return clean_df

        except Exception as e:
            log.error(f"[EXCEL INGEST ERROR] Failed to parse file [{file_path}]: {str(e)}")
            raise

    def inspect_response(self, payload: Dict[str, Any], error_cfg: Optional[Dict[str, Any]]) -> None:
        """No response inspection required for file ingestion."""
        pass

    @staticmethod
    def _clean_header(col_name: str) -> str:
        """Converts unstandardized header titles to clean snake_case format."""
        s = col_name.strip().lower()
        s = re.sub(r"[áàảãạăắằẳẵặâấầẩẫậ]", "a", s)
        s = re.sub(r"[éèẻẽẹêếềểễệ]", "e", s)
        s = re.sub(r"[iíìỉĩị]", "i", s)
        s = re.sub(r"[óòỏõọôốồổỗộơớờởỡợ]", "o", s)
        s = re.sub(r"[úùủũụưứừửữự]", "u", s)
        s = re.sub(r"[ýỳỷỹỵ]", "y", s)
        s = re.sub(r"[đ]", "d", s)
        s = re.sub(r"[^\w\s]", "", s)
        s = re.sub(r"\s+", "_", s)
        return s or "col_unnamed"