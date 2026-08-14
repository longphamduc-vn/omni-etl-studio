from typing import List
import pandas as pd

from core.common.exceptions import FilterError
from core.common.logger import log
from core.common.schemas import FilterCondition


class FilterEngine:
    """Engine for pre-call or post-fetch record filtering supporting multiple evaluation operators."""

    @staticmethod
    def apply_filters(df: pd.DataFrame, conditions: List[FilterCondition]) -> pd.DataFrame:
        """Applies a sequence of filter conditions on a Pandas DataFrame."""
        if df.empty or not conditions:
            return df

        filtered_df = df.copy()

        try:
            for cond in conditions:
                field = cond.field
                op = cond.operator.upper()
                val = cond.value

                if field not in filtered_df.columns:
                    log.warning(f"Filter field '{field}' not found in DataFrame columns. Skipping rule.")
                    continue

                col_series = filtered_df[field]

                # Automatic numeric casting for arithmetic comparison operators
                if op in [">", "<", ">=", "<="]:
                    try:
                        col_series = pd.to_numeric(col_series)
                        val = float(val) if not isinstance(val, (int, float)) else val
                    except (ValueError, TypeError):
                        pass

                if op in ["==", "="]:
                    filtered_df = filtered_df[col_series.astype(str) == str(val)]
                elif op in ["!=", "<>"]:
                    filtered_df = filtered_df[col_series.astype(str) != str(val)]
                elif op == ">":
                    filtered_df = filtered_df[col_series > val]
                elif op == "<":
                    filtered_df = filtered_df[col_series < val]
                elif op == ">=":
                    filtered_df = filtered_df[col_series >= val]
                elif op == "<=":
                    filtered_df = filtered_df[col_series <= val]
                elif op == "IN":
                    val_list = val if isinstance(val, list) else [val]
                    val_str_list = [str(v) for v in val_list]
                    filtered_df = filtered_df[col_series.astype(str).isin(val_str_list)]
                elif op == "NOT IN":
                    val_list = val if isinstance(val, list) else [val]
                    val_str_list = [str(v) for v in val_list]
                    filtered_df = filtered_df[~col_series.astype(str).isin(val_str_list)]
                elif op == "CONTAINS":
                    filtered_df = filtered_df[
                        col_series.astype(str).str.contains(str(val), na=False)
                    ]
                else:
                    raise FilterError(f"Unsupported filter operator: {op}")

            return filtered_df

        except Exception as e:
            raise FilterError(f"FilterEngine execution error: {str(e)}")