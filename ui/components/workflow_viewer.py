import streamlit as st
from core.common.schemas import WorkflowConfig


def render_workflow_flow(workflow_config: WorkflowConfig):
    """Renders a clean and compact step-by-step pipeline execution visual flow structure."""
    with st.expander(f"📌 Pipeline Steps Diagram ({len(workflow_config.steps)} Steps Configured)", expanded=False):
        st.caption(f"**Catalog ID:** `{workflow_config.workflow_id}` | **Description:** {workflow_config.description or 'N/A'}")
        
        cols = st.columns(min(len(workflow_config.steps), 3))
        for idx, step in enumerate(workflow_config.steps):
            col = cols[idx % len(cols)]
            with col:
                with st.container(border=True):
                    st.markdown(f"**Step {idx+1}:** `{step.step_id}`")
                    st.caption(f"**Method/Driver:** `{step.method}` / `{step.driver}`")
                    st.caption(f"**Output Table:** `{step.output_dataset}`")
                    if step.transformations:
                        ops = ", ".join([f"`{t.operator}`" for t in step.transformations])
                        st.caption(f"**Transforms:** {ops}")