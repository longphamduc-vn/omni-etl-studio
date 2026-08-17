# Filepath: ui/views/execution_view.py
# Updated_at: 2026-08-16 23:45:00
# Description: Fixed session persistence preserving auth headers across pipeline executions.

from typing import Optional
import streamlit as st

from core.common.schemas import WorkflowConfig
from core.engine.runner import PipelineRunner
from core.lifecycle.init_handler import LifecycleHandler
from core.registry.workflow_registry import WorkflowRegistry
from ui.components.input_builder import render_dynamic_inputs
from ui.components.retry_modal import RetryPanelComponent
from ui.components.workflow_flow import render_workflow_flow


def render_execution_tab(selected_workflow: Optional[WorkflowConfig], registry: WorkflowRegistry) -> None:
    """Renders the execution tab ensuring session auth headers are properly injected before execution."""
    if not selected_workflow:
        st.info("Vui lòng chọn một Workflow từ Sidebar để bắt đầu.")
        return

    # Header Controls
    col_title, col_btn = st.columns([0.75, 0.25])
    with col_title:
        st.title(f"⚡ {getattr(selected_workflow, 'workflow_name', '') or selected_workflow.workflow_id}")
        st.caption(f"Pipeline ID: `{selected_workflow.workflow_id}` | Domain Path: `{selected_workflow.domain_path}`")

    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        run_btn = st.button("▶ EXECUTE PIPELINE", type="primary", width="stretch")

    st.divider()

    # Render DAG Diagram & Inputs
    render_workflow_flow(selected_workflow)
    global_input = render_dynamic_inputs(selected_workflow.inputs)

    # --------------------------------------------------------------------------
    # 1. LOAD & PERSIST DOMAIN SESSION TOKEN
    # --------------------------------------------------------------------------
    domain_key = selected_workflow.domain_path or "general"
    session_store_key = f"domain_session_{domain_key}"

    if session_store_key not in st.session_state:
        with st.spinner(f"🔑 Initializing Session for Domain [{domain_key}]..."):
            init_ctx = LifecycleHandler.load_domain_session(domain_key, registry)
            if init_ctx and getattr(init_ctx, "session", None):
                st.session_state[session_store_key] = dict(init_ctx.session)
                st.toast(f"✅ Session Auth Loaded for [{domain_key}]", icon="🔐")
            else:
                st.session_state[session_store_key] = {}

    # --------------------------------------------------------------------------
    # 2. INSTANTIATE RUNNER & INJECT SESSION
    # --------------------------------------------------------------------------
    runner = PipelineRunner(workflow=selected_workflow)
    
    # Ép buộc nạp Session Auth Token vào Context Runner
    active_session = st.session_state.get(session_store_key, {})
    if active_session:
        runner.context.session.update(active_session)

    # Handlers for Retry / Skip
    def handle_retry(step_id: str):
        with st.spinner(f"Retrying step '{step_id}'..."):
            # Đảm bảo vẫn giữ session khi retry
            runner.context.session.update(st.session_state.get(session_store_key, {}))
            context = runner.run(input_data=global_input, start_step_id=step_id)
            st.session_state["last_context"] = context
        st.rerun()

    def handle_skip(step_id: str):
        runner.context.exec_status = "RUNNING"
        st.rerun()

    # Render Panel Retry nếu gặp lỗi/tạm dừng
    active_ctx = st.session_state.get("last_context", runner.context)
    if active_ctx.exec_status in ["PAUSED", "PAUSED_WAITING_RETRY", "FAILED"]:
        RetryPanelComponent.render(active_ctx, handle_retry, handle_skip)

    # --------------------------------------------------------------------------
    # 3. TRIGGER PIPELINE EXECUTION
    # --------------------------------------------------------------------------
    if run_btn:
        with st.spinner(f"Executing pipeline '{selected_workflow.workflow_id}'..."):
            try:
                # Đảm bảo nạp lại session token trước khi run
                runner.context.session.update(st.session_state.get(session_store_key, {}))
                
                context = runner.run(input_data=global_input)
                st.session_state["last_context"] = context
                st.session_state["last_wf_config"] = selected_workflow

                if context.exec_status == "SUCCESS":
                    st.success("🎉 Pipeline execution completed successfully!")
                elif context.exec_status in ["PAUSED", "PAUSED_WAITING_RETRY", "FAILED"]:
                    st.warning(f"⚠️ Execution Paused: **{context.exec_status}**")

            except Exception as e:
                st.error(f"❌ Execution Failure: {str(e)}")

    # --------------------------------------------------------------------------
    # 4. OUTPUT DATASETS DISPLAY
    # --------------------------------------------------------------------------
    ctx_to_display = st.session_state.get("last_context", runner.context)
    datasets = getattr(ctx_to_display, "datasets", {})

    st.divider()
    st.subheader("📊 Output Datasets")

    if not datasets:
        st.info("Chưa có dataset nào được tạo ra.")
    else:
        for table_name, df in datasets.items():
            with st.expander(f"📋 Table: `{table_name}`", expanded=True):
                if df is not None and hasattr(df, "empty") and not df.empty:
                    st.dataframe(df, width="stretch")
                    st.caption(f"Total Rows: {len(df)} | Columns: {list(df.columns)}")
                else:
                    st.warning("Table rỗng (No data).")

    # --------------------------------------------------------------------------
    # 5. LIVE CONTEXT INSPECTOR (DEBUG)
    # --------------------------------------------------------------------------
    st.divider()
    st.subheader("🔍 Active Pipeline Context (Live JSON Inspector)")
    
    st.json({
        "run_id": getattr(ctx_to_display, "run_id", None),
        "workflow_id": getattr(ctx_to_display, "workflow_id", None),
        "exec_status": getattr(ctx_to_display, "exec_status", None),
        "session": getattr(ctx_to_display, "session", {}),
        "input_data": getattr(ctx_to_display, "input_data", {}),
        "step_states": getattr(ctx_to_display, "step_states", {}),
        "active_tables": list(getattr(ctx_to_display, "datasets", {}).keys()) if hasattr(ctx_to_display, "datasets") else [],
    })