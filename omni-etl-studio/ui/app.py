import streamlit as st

from core.registry.workflow_registry import WorkflowRegistry
from core.engine.runner import PipelineRunner
from ui.components.workflow_viewer import render_workflow_flow
from ui.components.data_inspector import render_data_inspector
from ui.components.converter_widget import render_converter_widget

# Page Settings
st.set_page_config(page_title="OmniETL Studio", page_icon="🚀", layout="wide")

# Cached Registry Initialization
@st.cache_resource
def get_registry():
    return WorkflowRegistry()

registry = get_registry()

st.title("🚀 OmniETL Studio Web Console")
st.caption("Declarative Multi-Protocol ETL Engine Powered by DuckDB")

# Sidebar Control Panel
st.sidebar.header("🛠️ Pipeline Control")
available_workflows = list(registry._registry.keys())

if not available_workflows:
    st.sidebar.error("No workflows registered in catalog.json")
    st.stop()

selected_wf_id = st.sidebar.selectbox("Select Workflow:", available_workflows)
workflow_config = registry.get_workflow(selected_wf_id)

st.sidebar.markdown("---")
st.sidebar.subheader("🌐 Global Dynamic Inputs")
dept_code = st.sidebar.text_input("dept_code", value="CS")
warehouse_id = st.sidebar.text_input("warehouse_id", value="WH-01")

global_input = {"dept_code": dept_code, "warehouse_id": warehouse_id}

# Navigation Tabs
tab_pipeline, tab_converter = st.tabs(["📋 Pipeline Execution", "🔄 Nexacro Converter Tool"])

with tab_pipeline:
    # 1. Render Workflow Steps Structure
    render_workflow_flow(workflow_config)

    st.markdown("---")
    # 2. Pipeline Execution Trigger
    if st.button("▶ Execute Pipeline", type="primary", use_container_width=True):
        with st.spinner(f"Running pipeline '{selected_wf_id}'..."):
            try:
                runner = PipelineRunner(workflow=workflow_config)
                context = runner.run(global_input=global_input)
                st.success("🎉 Pipeline execution completed successfully!")

                # 3. Render DuckDB Data Inspector
                render_data_inspector(context, workflow_config)
                context.close()

            except Exception as e:
                st.error(f"❌ Pipeline Execution Error: {str(e)}")

with tab_converter:
    # 4. Render Nexacro XML Converter Utility
    render_converter_widget()