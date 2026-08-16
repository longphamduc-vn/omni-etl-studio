from typing import Any, Dict, List
import pandas as pd
import streamlit as st
from core.common.schemas import WorkflowInput


def render_dynamic_inputs(inputs_config: List[WorkflowInput]) -> Dict[str, Any]:
    """Renders dynamic user input controls on the main body page based on WorkflowInput definitions."""
    user_inputs: Dict[str, Any] = {}

    if not inputs_config:
        st.info("ℹ️ Kịch bản này không yêu cầu tham số đầu vào.")
        return user_inputs

    st.markdown("### ⚙️ Workflow Input Parameters")
    cols = st.columns(min(len(inputs_config), 2))

    for idx, inp in enumerate(inputs_config):
        col = cols[idx % len(cols)]
        label = inp.label or inp.name
        help_text = inp.description
        input_type = (inp.type or "string").lower()

        with col:
            if input_type in ["table", "grid", "array"]:
                st.markdown(f"**{label}**")
                if help_text:
                    st.caption(help_text)

                default_data = inp.default if isinstance(inp.default, list) else []
                df_init = pd.DataFrame(default_data)

                if df_init.empty and inp.columns:
                    col_names = [c.name or c.field for c in inp.columns if c.name or c.field]
                    df_init = pd.DataFrame(columns=col_names)

                edited_df = st.data_editor(
                    df_init,
                    num_rows="dynamic",
                    use_container_width=True,
                    key=f"input_table_{inp.name}"
                )
                user_inputs[inp.name] = edited_df.to_dict(orient="records")

            elif input_type in ["string", "text"]:
                val = st.text_input(
                    label=label,
                    value=str(inp.default if inp.default is not None else ""),
                    help=help_text,
                    key=f"input_{inp.name}"
                )
                user_inputs[inp.name] = val

            elif input_type in ["number", "int", "float"]:
                default_val = float(inp.default) if inp.default is not None else 0.0
                val = st.number_input(
                    label=label,
                    value=default_val,
                    help=help_text,
                    key=f"input_{inp.name}"
                )
                user_inputs[inp.name] = val

            elif input_type in ["select", "dropdown"] and inp.options:
                default_idx = 0
                if inp.default in inp.options:
                    default_idx = inp.options.index(inp.default)
                val = st.selectbox(
                    label=label,
                    options=inp.options,
                    index=default_idx,
                    help=help_text,
                    key=f"input_{inp.name}"
                )
                user_inputs[inp.name] = val

            else:
                val = st.text_input(
                    label=label,
                    value=str(inp.default or ""),
                    help=help_text,
                    key=f"input_{inp.name}"
                )
                user_inputs[inp.name] = val

    return user_inputs