# Filepath: ui/components/tree_navigation.py
# Updated_at: 2026-08-16 21:00:00
# Description: Folder tree navigation component with styled hierarchy.

from typing import Any, Dict, Optional
import streamlit as st
from core.common.schemas import WorkflowConfig


class TreeNavigationComponent:
    """Component for rendering recursive folder tree navigation in sidebar."""

    @classmethod
    def render(cls, tree_data: Dict[str, Any], depth: int = 0) -> Optional[WorkflowConfig]:
        """Renders tree folder nodes cleanly."""
        selected_wf = None

        for node_name, content in tree_data.items():
            if isinstance(content, dict) and "__workflows__" in content:
                workflows = content.get("__workflows__", [])
                subfolders = {k: v for k, v in content.items() if k != "__workflows__"}

                # Folder Node
                with st.expander(f"📁 {node_name}", expanded=(depth == 0)):
                    for wf in workflows:
                        if isinstance(wf, WorkflowConfig):
                            # Leaf Workflow Button
                            btn_label = f"⚡ {wf.workflow_id}"
                            is_active = st.session_state.get("selected_wf_id") == wf.workflow_id
                            
                            if st.button(
                                btn_label,
                                key=f"nav_{wf.domain_path}_{wf.workflow_id}",
                                use_container_width=True,
                                type="primary" if is_active else "secondary"
                            ):
                                st.session_state["selected_workflow"] = wf
                                st.session_state["selected_wf_id"] = wf.workflow_id
                                st.rerun()

                    if subfolders:
                        sub_sel = cls.render(subfolders, depth=depth + 1)
                        if sub_sel:
                            selected_wf = sub_sel

            elif isinstance(content, dict):
                with st.expander(f"📂 {node_name}", expanded=False):
                    sub_sel = cls.render(content, depth=depth + 1)
                    if sub_sel:
                        selected_wf = sub_sel

        return st.session_state.get("selected_workflow", selected_wf)