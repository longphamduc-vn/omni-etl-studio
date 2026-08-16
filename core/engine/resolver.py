import re
from typing import Any, Dict, List, Optional
import pandas as pd
from core.storage.context import PipelineContext


class VariableResolver:
    """Resolves variable specifications into parameters and dataset structures for Drivers."""

    @staticmethod
    def resolve(
        var_config: Dict[str, Any], 
        context: PipelineContext, 
        global_context: Optional[Dict[str, Any]] = None,
        current_loop_row: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        resolved_params: Dict[str, Any] = {}
        resolved_datasets: Dict[str, List[Dict[str, Any]]] = {}

        for var_name, config in var_config.items():
            # Convert Pydantic object to dict if necessary
            cfg = config.dict() if hasattr(config, "dict") else config
            is_dataset = cfg.get("type") == "dataset"

            if is_dataset:
                resolved_datasets[var_name] = VariableResolver._resolve_dataset(
                    cfg, context, global_context or {}, current_loop_row
                )
            else:
                source_path = cfg.get("source") or cfg.get("jsonpath", "")
                resolved_params[var_name] = VariableResolver._resolve_scalar(
                    source_path, context, global_context or {}, current_loop_row
                )

        return {"parameters": resolved_params, "datasets": resolved_datasets}

    @staticmethod
    def _resolve_scalar(
        path: str, 
        context: PipelineContext, 
        global_context: Dict[str, Any], 
        current_loop_row: Optional[Dict[str, Any]]
    ) -> Any:
        raw_val = VariableResolver._extract_by_path(path, context, global_context, current_loop_row)
        if isinstance(raw_val, list) and len(raw_val) > 0:
            return raw_val[0]
        return raw_val

    @staticmethod
    def _resolve_dataset(
        config: Dict[str, Any], 
        context: PipelineContext, 
        global_context: Dict[str, Any], 
        current_loop_row: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        columns_def = config.get("columns", [])
        if not columns_def:
            return []

        extracted_cols: Dict[str, List[Any]] = {}
        max_rows = 1

        for col_def in columns_def:
            c_cfg = col_def.dict() if hasattr(col_def, "dict") else col_def
            field_path = c_cfg.get("field") or c_cfg.get("name", "")
            alias = c_cfg.get("alias") or VariableResolver._clean_alias(field_path)

            val = VariableResolver._extract_by_path(field_path, context, global_context, current_loop_row)

            if isinstance(val, (list, pd.Series)):
                col_values = list(val)
                max_rows = max(max_rows, len(col_values))
            elif isinstance(val, pd.DataFrame):
                col_values = val.iloc[:, 0].tolist() if not val.empty else []
                max_rows = max(max_rows, len(col_values))
            else:
                col_values = [val] if val is not None else []

            extracted_cols[alias] = col_values

        if not extracted_cols:
            return []

        result_rows: List[Dict[str, Any]] = []
        for i in range(max_rows):
            row_dict = {}
            for col_name, val_list in extracted_cols.items():
                if i < len(val_list):
                    row_dict[col_name] = val_list[i]
                elif len(val_list) == 1:
                    row_dict[col_name] = val_list[0]
                else:
                    row_dict[col_name] = None
            result_rows.append(row_dict)

        return result_rows

    @staticmethod
    def _extract_by_path(
        path: str, 
        context: PipelineContext, 
        global_context: Dict[str, Any], 
        current_loop_row: Optional[Dict[str, Any]]
    ) -> Any:
        if not path:
            return None

        # 1. Namespace loop_row
        if path.startswith("loop_row"):
            sub_path = path.replace("loop_row.", "").replace("loop_row", "")
            return VariableResolver._get_nested_value(current_loop_row or {}, sub_path)

        # 2. Namespace global_input
        if path.startswith("global_input"):
            sub_path = path.replace("global_input.", "").replace("global_input", "")
            input_data = global_context.get("global_input", {})
            return VariableResolver._get_nested_value(input_data, sub_path)

        # 3. Namespace session
        if path.startswith("session"):
            sub_path = path.replace("session.", "").replace("session", "")
            session_data = global_context.get("session", {})
            return VariableResolver._get_nested_value(session_data, sub_path)

        # 4. Namespace stepX (Truy vấn từ DuckDB Context)
        parts = path.split(".", 1)
        step_id = parts[0]
        field_attr = parts[1] if len(parts) > 1 else ""

        # Bỏ chữ '.output' nếu người dùng gõ step1.output.product_id
        if field_attr.startswith("output."):
            field_attr = field_attr.replace("output.", "", 1)

        table_data = context.get_dataframe(step_id)
        if table_data is not None and isinstance(table_data, pd.DataFrame):
            clean_field, idx = VariableResolver._parse_array_idx(field_attr)
            if clean_field in table_data.columns:
                series_vals = table_data[clean_field].tolist()
                if idx is not None:
                    return series_vals[idx] if 0 <= idx < len(series_vals) else None
                return series_vals

        return None

    @staticmethod
    def _get_nested_value(data: Any, path: str) -> Any:
        if not path:
            return data
        
        clean_path, idx = VariableResolver._parse_array_idx(path)
        parts = clean_path.split(".")
        curr = data

        for p in parts:
            if isinstance(curr, dict) and p in curr:
                curr = curr[p]
            elif isinstance(curr, list):
                if p.isdigit():
                    idx_p = int(p)
                    curr = curr[idx_p] if 0 <= idx_p < len(curr) else None
                else:
                    curr = [item.get(p) for item in curr if isinstance(item, dict) and p in item]
            else:
                return None

        if idx is not None and isinstance(curr, list):
            return curr[idx] if 0 <= idx < len(curr) else None

        return curr

    @staticmethod
    def _parse_array_idx(path: str):
        match = re.search(r"^(.*)\[(\d+)\]$", path)
        if match:
            return match.group(1), int(match.group(2))
        return path, None

    @staticmethod
    def _clean_alias(field_path: str) -> str:
        clean_path, _ = VariableResolver._parse_array_idx(field_path)
        return clean_path.split(".")[-1]