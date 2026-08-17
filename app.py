# Filepath: app.py
# Updated_at: 2026-08-16 20:51:30
# Description: Streamlit Entry Point for OmniETL Studio.

import streamlit as st

from core.registry.workflow_registry import WorkflowRegistry
from ui import apply_theme, render_sidebar
from ui.views import (
    render_converter_tab,
    render_duckdb_tab,
    render_editor_tab,
    render_execution_tab,
)

# 1. Page Configuration & Custom Theme Application
st.set_page_config(page_title="OmniETL Studio", page_icon="⚡", layout="wide")
apply_theme()


# 2. Cached Workflow Registry Initialization
@st.cache_resource
def get_registry() -> WorkflowRegistry:
    return WorkflowRegistry(root_dir="workflows")


registry = get_registry()

# 3. Sidebar Navigation & Active Workflow State Selection
selected_workflow = render_sidebar(registry)

# 4. Main Workspace Layout Tabs
tab_pipeline, tab_editor, tab_duckdb, tab_converter = st.tabs([
    "📋 Pipeline Execution",
    "🛠️ Workflow Studio (JSON Editor)",
    "🦆 DuckDB Data Explorer",
    "🔄 Nexacro XML Utility",
])

# 5. Render Selected Tab Workspace
with tab_pipeline:
    render_execution_tab(selected_workflow, registry)

with tab_editor:
    render_editor_tab(registry)

with tab_duckdb:
    render_duckdb_tab(context=st.session_state.get("last_context"))

with tab_converter:
    render_converter_tab()