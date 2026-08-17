# Filepath: ui/components/url_sync.py
# Updated_at: 2026-08-16 20:49:10
# Description: URL query parameters state manager.

# Filepath: ui/components/url_sync.py
# Updated_at: 2026-08-16 20:50:00
# Description: URL query parameters state manager.

import streamlit as st


class UrlSyncManager:
    """Synchronizes workflow state with browser query parameters."""

    @staticmethod
    def set_params(domain_path: str, flow_id: str) -> None:
        """Sets domain_path and flow_id in browser URL query parameters."""
        st.query_params["domain_path"] = domain_path
        st.query_params["flow_id"] = flow_id

    @staticmethod
    def get_params() -> dict:
        """Retrieves active query parameters from URL."""
        return {
            "domain_path": st.query_params.get("domain_path", None),
            "flow_id": st.query_params.get("flow_id", None),
        }