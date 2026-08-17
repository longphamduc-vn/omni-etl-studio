# Filepath: ui/components/presentation_grid.py
# Updated_at: 2026-08-16 20:49:10
# Description: DataFrame presentation grid and audit output renderer.

# Filepath: ui/components/presentation_grid.py
# Updated_at: 2026-08-16 20:50:00
# Description: DataFrame presentation grid and audit output renderer.

from typing import Any
import streamlit as st
from core.common.schemas import WorkflowConfig


class PresentationGridComponent:
    """Renders step outputs and DataFrames."""

    @staticmethod
    def render_dataframe(df: Any, title: str = "Dataset Output") -> None:
        """Displays DataFrame in Streamlit UI."""
        st.subheader(title)
        if df is not None and hasattr(df, "empty") and not df.empty:
            st.dataframe(df, use_container_width=True)
        else:
            st.info("Dataset is empty.")


def render_step_outputs_and_audit(context: Any, workflow: WorkflowConfig) -> None:
    """Renders execution step outputs and audit logs from context."""
    st.markdown("---")
    st.subheader("📊 Pipeline Execution Outputs")

    if not context or not hasattr(context, "datasets"):
        st.info("No output datasets available.")
        return

    datasets = getattr(context, "datasets", {})
    if not datasets:
        st.info("No datasets generated.")
        return

    for table_name, df in datasets.items():
        with st.expander(f"📁 Dataset Table: `{table_name}`", expanded=True):
            PresentationGridComponent.render_dataframe(df, title=f"Table: {table_name}")