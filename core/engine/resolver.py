# ==============================================================================
# Filepath: core/engine/resolver.py
# Updated_at: 2026-08-16 17:26:43
# Description: Resolves dynamic variables and Jinja2 templates into driver payloads.
# ==============================================================================

import re
from typing import Any, Dict, List, Optional
import pandas as pd

from core.storage.context import PipelineContext


class VariableResolver:
    """Resolves variable mapping definitions for Driver invocation and API payloads."""

    @staticmethod
    def resolve(
        var_config: Dict[str, Any],
        context: PipelineContext,
        loop_row: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Resolves variable maps into parameters and structured datasets for Drivers."""
        res_params: Dict[str, Any] = {}
        res_datasets: Dict[str, List[Dict[str, Any]]] = {}

        if not var_config:
            return {"parameters": res_params, "datasets": res_datasets}

        global_scope = {
            "inputs": getattr(context, "input_data", {}),
            "session": getattr(context, "session", {}),
            "loop_row": loop_row or {},
        }

        for var_name, config in var_config.items():
            cfg = config.model_dump() if hasattr(config, "model_dump") else config
            var_type = cfg.get("type", "parameter")

            if var_type == "dataset":
                res_datasets[var_name] = VariableResolver._resolve_dataset(
                    cfg, context, global_scope
                )
            else:
                source_path = cfg.get("source") or cfg.get("jsonpath", "")
                res_params[var_name] = VariableResolver._resolve_scalar(
                    source_path, context, global_scope, cfg.get("default")
                )

        return {"parameters": res_params, "datasets": res_datasets}

    @staticmethod
    def _resolve_scalar(
        path: str, context: PipelineContext, scope: Dict[str, Any], default_val: Any
    ) -> Any:
        raw_val = VariableResolver._extract_path(path, context, scope)
        if raw_val is None:
            return default_val
        if isinstance(raw_val, list) and len(raw_val) > 0:
            return raw_val[0]
        return raw_val

    @staticmethod
    def _resolve_dataset(
        cfg: Dict[str, Any], context: PipelineContext, scope: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        cols_def = cfg.get("columns", [])
        if not cols_def:
            return []

        col_data: Dict[str, List[Any]] = {}
        max_rows = 1

        for c_def in cols_def:
            c_cfg = c_def.model_dump() if hasattr(c_def, "model_dump") else c_def
            field_path = c_cfg.get("field") or c_cfg.get("name", "")
            alias = c_cfg.get("alias") or VariableResolver._clean_alias(field_path)

            val = VariableResolver._extract_path(field_path, context, scope)

            if isinstance(val, (list, pd.Series)):
                vals = list(val)
                max_rows = max(max_rows, len(vals))
            elif isinstance(val, pd.DataFrame):
                vals = val.iloc[:, 0].tolist() if not val.empty else []
                max_rows = max(max_rows, len(vals))
            else:
                vals = [val] if val is not None else []

            col_data[alias] = vals

        rows: List[Dict[str, Any]] = []
        for i in range(max_rows):
            row_dict = {}
            for col_name, val_list in col_data.items():
                if i < len(val_list):
                    row_dict[col_name] = val_list[i]
                elif len(val_list) == 1:
                    row_dict[col_name] = val_list[0]
                else:
                    row_dict[col_name] = None
            rows.append(row_dict)

        return rows

    @staticmethod
    def _extract_path(path: str, context: PipelineContext, scope: Dict[str, Any]) -> Any:
        if not path:
            return None

        # Scope 1: loop_row namespace
        if path.startswith("loop_row"):
            sub_path = path.replace("loop_row.", "").replace("loop_row", "")
            return VariableResolver._get_nested(scope.get("loop_row", {}), sub_path)

        # Scope 2: inputs namespace
        if path.startswith("global_input") or path.startswith("inputs"):
            sub_path = re.sub(r"^(global_input|inputs)\.?", "", path)
            return VariableResolver._get_nested(scope.get("inputs", {}), sub_path)

        # Scope 3: session namespace
        if path.startswith("session"):
            sub_path = path.replace("session.", "").replace("session", "")
            return VariableResolver._get_nested(scope.get("session", {}), sub_path)

        # Scope 4: Step table extraction from DuckDB Context
        parts = path.split(".", 1)
        step_id = parts[0]
        attr = parts[1] if len(parts) > 1 else ""

        if attr.startswith("output."):
            attr = attr.replace("output.", "", 1)

        try:
            df = context.get_dataframe(step_id)
            if df is not None and not df.empty:
                clean_attr, idx = VariableResolver._parse_idx(attr)
                if clean_attr in df.columns:
                    col_vals = df[clean_attr].tolist()
                    if idx is not None:
                        return col_vals[idx] if 0 <= idx < len(col_vals) else None
                    return col_vals
        except Exception:
            pass

        return None

    @staticmethod
    def _get_nested(data: Any, path: str) -> Any:
        if not path:
            return data

        clean_path, idx = VariableResolver._parse_idx(path)
        parts = clean_path.split(".")
        curr = data

        for p in parts:
            if isinstance(curr, dict) and p in curr:
                curr = curr[p]
            elif isinstance(curr, list):
                if p.isdigit():
                    i = int(p)
                    curr = curr[i] if 0 <= i < len(curr) else None
                else:
                    curr = [item.get(p) for item in curr if isinstance(item, dict) and p in item]
            else:
                return None

        if idx is not None and isinstance(curr, list):
            return curr[idx] if 0 <= idx < len(curr) else None

        return curr

    @staticmethod
    def _parse_idx(path: str):
        match = re.search(r"^(.*)\[(\d+)\]$", path)
        if match:
            return match.group(1), int(match.group(2))
        return path, None

    @staticmethod
    def _clean_alias(field_path: str) -> str:
        clean_path, _ = VariableResolver._parse_idx(field_path)
        return clean_path.split(".")[-1]