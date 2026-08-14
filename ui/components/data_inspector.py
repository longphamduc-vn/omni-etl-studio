import pandas as pd
import streamlit as st

from core.common.schemas import WorkflowConfig
from core.engine.evaluator import VariableEvaluator
from core.storage.context import PipelineContext
from drivers.nexacro.builder import NexacroBuilder


def render_step_outputs_and_audit(context: PipelineContext, workflow_config: WorkflowConfig):
    """Render output tables and dynamic audit payload logs (XML & Structured JSON) separately for EVERY step."""
    st.markdown("---")
    st.subheader("📊 EXECUTION RESULTS BY STEP")

    # Fetch global_input context from session state
    global_input = st.session_state.get("last_global_input", {})
    global_context = {"global_input": global_input}

    for idx, step in enumerate(workflow_config.steps, 1):
        with st.container(border=True):
            # Step Header Line with Execution Metadata
            c_title, c_dl = st.columns([0.75, 0.25])
            
            with c_title:
                st.markdown(
                    f"#### Step {idx}: `{step.step_id}` "
                    f"&nbsp;<span style='font-size:12px; color:gray;'>({step.driver.upper()} | {step.method} | {step.mode})</span>",
                    unsafe_allow_html=True
                )
            
            # Fetch Step Result Dataset from DuckDB
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

            # Sub-tabs for Clean UI Presentation
            tab_data, tab_audit_xml, tab_audit_json = st.tabs([
                "📋 Data Table Output", 
                "📜 XML Payload Sent", 
                "🔗 JSON Payload Representation"
            ])

            # Resolve variables dynamically against context
            try:
                resolved_vars = VariableEvaluator.evaluate_all(step.variables or {}, global_context)
            except Exception:
                resolved_vars = {}

            # 1. TAB OUTPUT DATA TABLE
            with tab_data:
                if not df_step.empty:
                    st.dataframe(df_step, use_container_width=True)
                else:
                    st.info(f"No result records found in table `{step.output_dataset}`.")

            # 2. TAB AUDIT XML PAYLOAD
            with tab_audit_xml:
                st.caption("**Nexacro XML Protocol Payload (Sent to Endpoint):**")
                if step.driver == "nexacro":
                    try:
                        actual_xml = NexacroBuilder.build_xml_payload(resolved_vars)
                        st.code(actual_xml, language="xml")
                    except Exception as e:
                        st.error(f"Failed to build XML payload: {str(e)}")
                else:
                    st.info(f"Driver `{step.driver}` does not generate XML payloads.")

            # 3. TAB AUDIT STRUCTURED JSON PAYLOAD
            with tab_audit_json:
                st.caption("**Nexacro Structured JSON Payload:**")
                structured_payload = NexacroBuilder.prepare_structured_payload(resolved_vars)
                
                st.json({
                    "step_id": step.step_id,
                    "driver": step.driver,
                    "method": step.method,
                    "endpoint": step.endpoint or "N/A (Pure Transformation)",
                    "payload": structured_payload
                })