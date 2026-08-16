from typing import Any, Dict
import pandas as pd
import streamlit as st

from core.common.schemas import WorkflowConfig
from core.engine.resolver import VariableResolver
from core.storage.context import PipelineContext
from drivers.nexacro import NexacroDriver


def render_step_output(step_config: Dict[str, Any], df_result: pd.DataFrame):
    """Renders DataFrame results based on step output_config."""
    output_config = step_config.get("output_config", {})
    display_title = output_config.get("display_title", f"Output: {step_config.get('step_id')}")
    columns_config = output_config.get("columns", [])

    st.subheader(display_title)

    if df_result is None or df_result.empty:
        st.warning("Không có dữ liệu trả về.")
        return

    display_df = df_result.copy()

    if columns_config:
        visible_cols = [
            c["field"] for c in columns_config 
            if c.get("visible", True) and c.get("field") in display_df.columns
        ]
        if visible_cols:
            display_df = display_df[visible_cols]

        rename_map = {
            c["field"]: c["title"] 
            for c in columns_config 
            if "title" in c and c.get("field") in display_df.columns
        }
        display_df = display_df.rename(columns=rename_map)

    st.dataframe(display_df, use_container_width=True)


def render_step_outputs_and_audit(context: PipelineContext, workflow_config: WorkflowConfig):
    """Render output tables and dynamic audit payload logs (XML & Structured JSON) separately for EVERY step."""
    st.markdown("---")
    st.subheader("📊 EXECUTION RESULTS BY STEP")

    global_input = st.session_state.get("last_global_input", {})
    global_context = {"global_input": global_input}

    for idx, step in enumerate(workflow_config.steps, 1):
        with st.container(border=True):
            c_title, c_dl = st.columns([0.75, 0.25])
            
            with c_title:
                st.markdown(
                    f"#### Step {idx}: `{step.step_id}` "
                    f"&nbsp;<span style='font-size:12px; color:gray;'>({step.driver.upper()} | {step.method} | {step.mode})</span>",
                    unsafe_allow_html=True
                )
            
            try:
                df_step = context.get_dataframe(step.output_dataset)
                rows_cnt = len(df_step)
            except Exception:
                df_step = pd.DataFrame()
                rows_cnt = 0

            with c_dl:
                if not df_step.empty:
                    st.download_button(
                        label=f"📥 Export CSV ({rows_cnt} rows)",
                        data=df_step.to_csv(index=False),
                        file_name=f"{step.step_id}_{step.output_dataset}.csv",
                        mime="text/csv",
                        key=f"btn_dl_step_{step.step_id}_{idx}",
                        use_container_width=True
                    )

            tab_data, tab_audit_xml, tab_audit_json = st.tabs([
                "📋 Data Table Output", 
                "📜 XML Payload Sent", 
                "🔗 JSON Payload Representation"
            ])

            # Resolve variables dynamically against context
            try:
                resolved_vars = VariableResolver.resolve(step.variables or {}, context, global_context)
            except Exception:
                resolved_vars = {"parameters": {}, "datasets": {}}

            # 1. TAB OUTPUT DATA TABLE
            with tab_data:
                render_step_output(step.model_dump(), df_step)

            # 2. TAB AUDIT XML PAYLOAD
            with tab_audit_xml:
                st.caption("**Nexacro XML Protocol Payload (Sent to Endpoint):**")
                if step.driver == "nexacro":
                    try:
                        actual_xml = NexacroDriver.build_xml_payload(resolved_vars)
                        st.code(actual_xml, language="xml")
                    except Exception as e:
                        st.error(f"Failed to build XML payload: {str(e)}")
                else:
                    st.info(f"Driver `{step.driver}` does not generate XML payloads.")

            # 3. TAB AUDIT STRUCTURED JSON PAYLOAD
            with tab_audit_json:
                st.caption("**Structured Variable Resolution:**")
                st.json({
                    "step_id": step.step_id,
                    "driver": step.driver,
                    "method": step.method,
                    "endpoint": step.endpoint or "N/A (Pure Transformation)",
                    "resolved_variables": resolved_vars
                })