import streamlit as st
from core.common.schemas import WorkflowConfig


def render_workflow_flow(workflow_config: WorkflowConfig):
    """Renders the step-by-step pipeline execution visual flow."""
    st.subheader(f"Workflow: `{workflow_config.workflow_id}`")
    st.info(f"**Description:** {workflow_config.description or 'No description provided.'}")

    st.markdown("### 📌 Pipeline Steps Flow")
    
    for idx, step in enumerate(workflow_config.steps, 1):
        mode_badge = "🔄 Chained Loop" if step.mode == "chained_loop" else "⚡ Batch"
        
        with st.expander(f"Step {idx}: `{step.step_id}` | Mode: {mode_badge} | Driver: `{step.driver}`", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Endpoint:** `{step.endpoint}`")
                st.write(f"**Output Dataset Table:** `{step.output_dataset}`")
            
            with col2:
                if step.variables:
                    st.write("**Variables Rules:**", list(step.variables.keys()))
                if step.filters:
                    st.write("**Filter Rules:**", len(step.filters), "conditions applied")

            if step.transformations:
                st.markdown("**DuckDB Transformations:**")
                op_names = [f"`{t.operator}`" for t in step.transformations]
                st.caption(" ➔ ".join(op_names))