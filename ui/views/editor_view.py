# Filepath: ui/views/editor_view.py
# Updated_at: 2026-08-16 21:00:00
# Description: Workflow Studio JSON editor view wrapper.

import json
import streamlit as st
from core.registry.workflow_registry import WorkflowRegistry


def render_editor_tab(registry: WorkflowRegistry) -> None:
    """Renders Tab 2: Workflow Studio JSON Editor View."""
    st.title("🛠️ Workflow Studio (JSON Editor)")
    st.caption("View and edit workflow raw configuration JSON definitions.")

    # Sửa từ list_workflows() sang list_workflows_grouped()
    grouped_workflows = registry.list_workflows_grouped()
    if not grouped_workflows:
        st.warning("No workflows available to edit.")
        return

    # Flatten danh sách workflows
    wf_options = {}
    for cat, wf_ids in grouped_workflows.items():
        for wf_id in wf_ids:
            wf = registry.get_workflow(wf_id)
            if wf:
                wf_options[f"{wf.domain_path} / {wf.workflow_id}"] = wf

    selected_key = st.selectbox("Select Workflow to Inspect/Edit:", list(wf_options.keys()))

    if selected_key:
        selected_wf = wf_options[selected_key]
        json_str = selected_wf.model_dump_json(indent=2)

        edited_json = st.text_area(
            "Workflow Specification (JSON)",
            value=json_str,
            height=450,
        )

        if st.button("💾 Save Configuration Changes", type="primary"):
            try:
                json.loads(edited_json)
                st.success(f"Config for '{selected_wf.workflow_id}' validated successfully!")
            except Exception as e:
                st.error(f"Invalid JSON Format: {str(e)}")