# Filepath: ui/components/input_builder.py
# Updated_at: 2026-08-16 23:59:00
# Description: Dynamic form builder supporting text, boolean, json, and interactive tables.

import json
from typing import Any, Dict, List
import pandas as pd
import streamlit as st
from core.common.schemas import InputDefinition


def render_dynamic_inputs(inputs: List[InputDefinition]) -> Dict[str, Any]:
    """Generates dynamic inputs for workflow global parameters."""
    input_values: Dict[str, Any] = {}

    if not inputs:
        return input_values

    valid_inputs = [inp for inp in inputs if isinstance(inp, InputDefinition) or hasattr(inp, "name")]
    if not valid_inputs:
        return input_values

    st.subheader("⚙️ Global Parameters")
    cols = st.columns(min(len(valid_inputs), 3))

    for idx, inp in enumerate(valid_inputs):
        col = cols[idx % len(cols)]
        with col:
            inp_name = getattr(inp, "name", f"param_{idx}")
            inp_label = getattr(inp, "label", None) or inp_name
            inp_type = getattr(inp, "type", "string")
            inp_desc = getattr(inp, "description", "")
            inp_req = getattr(inp, "required", False)
            inp_default = getattr(inp, "default", "")

            # Clean up label formatting
            clean_title = str(inp_label).replace("*", "").strip()
            display_label = f"{clean_title} *" if inp_req else clean_title

            # 1. TABLE INPUT TYPE (DATA EDITOR)
            if inp_type == "table":
                default_rows = inp_default if isinstance(inp_default, list) else []
                df_default = pd.DataFrame(default_rows)

                st.markdown(f"**{display_label}**")
                edited_df = st.data_editor(
                    df_default,
                    num_rows="dynamic",
                    width="stretch",
                    key=f"input_table_{inp_name}",
                )
                input_values[inp_name] = edited_df.to_dict(orient="records")

            # 2. JSON INPUT TYPE
            elif inp_type == "json":
                if isinstance(inp_default, (dict, list)):
                    formatted_default = json.dumps(inp_default, ensure_ascii=False, indent=2)
                else:
                    formatted_default = str(inp_default) if inp_default else "[]"

                raw_text = st.text_area(
                    display_label,
                    value=formatted_default,
                    help=f"{inp_desc} (Provide a valid JSON string)",
                    key=f"input_json_{inp_name}",
                    height=120,
                )
                try:
                    input_values[inp_name] = json.loads(raw_text)
                except Exception:
                    input_values[inp_name] = raw_text

            # 3. NUMBER INPUT TYPE
            elif inp_type == "integer":
                input_values[inp_name] = st.number_input(
                    display_label,
                    value=int(inp_default) if str(inp_default).isdigit() else 0,
                    help=inp_desc,
                    key=f"input_num_{inp_name}",
                )

            # 4. BOOLEAN INPUT TYPE
            elif inp_type == "boolean":
                input_values[inp_name] = st.checkbox(
                    display_label,
                    value=bool(inp_default),
                    help=inp_desc,
                    key=f"input_bool_{inp_name}",
                )

            # 5. STRING INPUT TYPE
            else:
                input_values[inp_name] = st.text_input(
                    display_label,
                    value=str(inp_default) if inp_default is not None else "",
                    help=inp_desc,
                    key=f"input_str_{inp_name}",
                )

    return input_values