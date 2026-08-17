# Filepath: ui/components/sidebar.py
# Updated_at: 2026-08-16 23:59:00
# Description: Clean sidebar navigation catalog free of Streamlit deprecation warnings.

from typing import Dict, Optional
import streamlit as st

from core.common.schemas import WorkflowConfig
from core.registry.workflow_registry import WorkflowRegistry


def render_sidebar(registry: WorkflowRegistry) -> Optional[WorkflowConfig]:
    """Renders the domain and workflow navigation tree in the sidebar."""
    with st.sidebar:
        st.title("🚀 OmniETL Studio")
        st.caption("Declarative Multi-Protocol Engine")
        st.divider()

        if st.button("🔄 Refresh Catalog", width="stretch"):
            registry.reload()
            st.session_state.clear()
            st.rerun()

        st.subheader("🌲 Workflows Catalog")

        grouped_workflows = registry.list_workflows_grouped()
        if not grouped_workflows:
            st.warning("⚠️ No workflows found in catalog.")
            return None

        domains = list(grouped_workflows.keys())
        current_wf = st.session_state.get("selected_workflow")
        
        default_domain_idx = 0
        if current_wf and current_wf.domain_path in domains:
            default_domain_idx = domains.index(current_wf.domain_path)

        selected_domain = st.selectbox(
            "📁 Select Domain Folder:",
            options=domains,
            index=default_domain_idx,
            format_func=lambda x: f"📁 {x}",
        )

        wf_ids_in_domain = grouped_workflows.get(selected_domain, [])
        wf_options: Dict[str, WorkflowConfig] = {}

        for wf_id in wf_ids_in_domain:
            wf = registry.get_workflow(wf_id)
            if wf:
                disp_name = getattr(wf, "workflow_name", None) or wf.workflow_id
                if not disp_name or str(disp_name).strip() == "":
                    disp_name = wf.workflow_id

                wf_options[f"⚡ {disp_name}"] = wf

        if not wf_options:
            st.info("No workflows found in this folder.")
            return None

        wf_labels = list(wf_options.keys())
        default_wf_idx = 0
        
        if current_wf:
            for idx, wf_obj in enumerate(wf_options.values()):
                if wf_obj.workflow_id == current_wf.workflow_id:
                    default_wf_idx = idx
                    break

        selected_label = st.selectbox(
            "📄 Select Workflow:",
            options=wf_labels,
            index=default_wf_idx,
        )

        selected_wf = wf_options[selected_label]
        st.session_state["selected_workflow"] = selected_wf
        st.session_state["selected_wf_id"] = selected_wf.workflow_id

        # Active metadata information card
        st.divider()
        active_title = getattr(selected_wf, "workflow_name", None) or selected_wf.workflow_id
        st.success(f"**Active Name:** `{active_title}`")
        st.caption(f"**Pipeline ID:** `{selected_wf.workflow_id}`")
        st.caption(f"**Domain Path:** `{selected_wf.domain_path}`")
        st.caption(f"**Total Steps:** {len(selected_wf.steps)}")

        return selected_wf