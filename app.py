import streamlit as st

from core.engine.runner import PipelineRunner
from core.registry.workflow_registry import WorkflowRegistry
from ui.components import (
    render_converter_widget,
    render_dynamic_inputs,
    render_duckdb_explorer_widget,
    render_step_outputs_and_audit,
    render_workflow_editor_widget,
    render_workflow_flow,
)

# Streamlit Page Setup
st.set_page_config(page_title="OmniETL Studio", page_icon="🚀", layout="wide")


@st.cache_resource
def get_registry():
    return WorkflowRegistry()


registry = get_registry()

# ==========================================
# 🛠️ SIDEBAR: WORKFLOW MANAGEMENT
# ==========================================
st.sidebar.title("🚀 OmniETL Studio")
st.sidebar.caption("Declarative Multi-Protocol Engine")
st.sidebar.markdown("---")

col_sb_ref, col_sb_cnt = st.sidebar.columns([0.4, 0.6])
with col_sb_ref:
    if st.button("🔄 Refresh", use_container_width=True):
        registry._scan_and_load_workflows()
        st.session_state.pop("last_context", None)
        st.rerun()

all_grouped_wf = registry.list_workflows_grouped()
total_wf_count = sum(len(v) for v in all_grouped_wf.values())

with col_sb_cnt:
    st.markdown(
        f"<div style='text-align: right; padding-top: 5px;'><b>{total_wf_count}</b> Workflows</div>", 
        unsafe_allow_html=True
    )

search_term = st.sidebar.text_input("🔍 Search Workflow:", placeholder="Type ID or keyword...").strip().lower()

filtered_grouped_wf = {}
for cat, wf_list in all_grouped_wf.items():
    matched = [wf_id for wf_id in wf_list if search_term in wf_id.lower()]
    if matched:
        filtered_grouped_wf[cat] = matched

if not filtered_grouped_wf:
    st.sidebar.warning("No matching workflows found.")
    st.stop()

categories = list(filtered_grouped_wf.keys())
selected_category = st.sidebar.selectbox("📁 Select Category / Folder:", options=categories)

available_wf_in_cat = filtered_grouped_wf[selected_category]
selected_wf_id = st.sidebar.selectbox("📄 Select Workflow Pipeline:", options=available_wf_in_cat)

workflow_config = registry.get_workflow(selected_wf_id)

st.sidebar.markdown("---")
st.sidebar.caption(f"**Active ID:** `{workflow_config.workflow_id}`")
st.sidebar.caption(f"**Steps Count:** {len(workflow_config.steps)}")

# ==========================================
# 📋 MAIN APPLICATION NAVIGATION TABS
# ==========================================
tab_pipeline, tab_editor, tab_duckdb, tab_converter = st.tabs([
    "📋 Pipeline Execution", 
    "🛠️ Workflow Studio (JSON Editor)", 
    "🦆 DuckDB Data Explorer", 
    "🔄 Nexacro XML Utility"
])

# ------------------------------------------
# TAB 1: PIPELINE EXECUTION CONSOLE
# ------------------------------------------
with tab_pipeline:
    top_col1, top_col2 = st.columns([0.7, 0.3])

    with top_col1:
        st.title("⚡ Execution Console")
        st.caption(f"Category: `{selected_category}` | Active Pipeline: **{workflow_config.workflow_id}**")

    with top_col2:
        st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
        run_btn = st.button("▶ EXECUTE FULL PIPELINE", type="primary", use_container_width=True)

    st.markdown("---")

    render_workflow_flow(workflow_config)
    global_input = render_dynamic_inputs(workflow_config.inputs)

    if run_btn:
        with st.spinner(f"Executing pipeline '{selected_wf_id}'..."):
            try:
                runner = PipelineRunner(workflow=workflow_config)
                context = runner.run(global_input=global_input)

                st.success("🎉 Pipeline execution completed successfully!")

                st.session_state["last_context"] = context
                st.session_state["last_wf_config"] = workflow_config
                st.session_state["last_global_input"] = global_input

            except Exception as e:
                st.error(f"❌ Pipeline Execution Failure: {str(e)}")

    if "last_context" in st.session_state and st.session_state.get("last_wf_config") == workflow_config:
        render_step_outputs_and_audit(st.session_state["last_context"], workflow_config)

# ------------------------------------------
# TAB 2: WORKFLOW JSON EDITOR & VALIDATOR
# ------------------------------------------
with tab_editor:
    render_workflow_editor_widget(registry)

# ------------------------------------------
# TAB 3: DUCKDB DATA EXPLORER & SQL LAB
# ------------------------------------------
with tab_duckdb:
    render_duckdb_explorer_widget()

# ------------------------------------------
# TAB 4: NEXACRO XML CONVERTER TOOL
# ------------------------------------------
with tab_converter:
    render_converter_widget()