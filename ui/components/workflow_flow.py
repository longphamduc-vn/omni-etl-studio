# Filepath: ui/components/workflow_flow.py
# Updated_at: 2026-08-16 20:49:10
# Description: DAG pipeline workflow flow visualization graph.

# Filepath: ui/components/workflow_flow.py
# Updated_at: 2026-08-16 20:50:00
# Description: DAG pipeline workflow flow visualization graph.

import streamlit as st
from core.common.schemas import WorkflowConfig


def render_workflow_flow(workflow: WorkflowConfig) -> None:
    """Renders a visual step pipeline flow for the selected workflow."""
    if not workflow or not workflow.steps:
        st.info("No step definitions available for this pipeline.")
        return

    st.subheader("📌 Pipeline DAG Flow")

    cols = st.columns(len(workflow.steps))
    for idx, step in enumerate(workflow.steps):
        with cols[idx]:
            driver_badge = f"`{step.driver}`"
            st.markdown(
                f"""
                <div style="background-color: #131c2e; border: 1px solid #1e293b; border-radius: 8px; padding: 10px; text-align: center;">
                    <div style="font-size: 0.75rem; color: #64748b;">Step {idx + 1}</div>
                    <div style="font-weight: 600; color: #f8fafc; font-size: 0.85rem; margin: 4px 0;">{step.step_id}</div>
                    <div style="font-size: 0.7rem; color: #60a5fa;">Driver: {driver_badge}</div>
                </div>
            """,
                unsafe_allow_html=True,
            )