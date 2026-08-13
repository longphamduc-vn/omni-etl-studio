import streamlit as st
import pandas as pd
from core.storage.context import PipelineContext
from core.common.schemas import WorkflowConfig


def render_data_inspector(context: PipelineContext, workflow_config: WorkflowConfig):
    """Renders the DuckDB isolated schema Inspector and DataFrame Exporter."""
    st.markdown("### 💾 DuckDB Storage Inspector")
    st.caption(f"Isolated Namespace: `{context.schema_name}`")

    # Select output table from pipeline steps
    available_tables = [step.output_dataset for step in workflow_config.steps if step.output_dataset]
    
    if not available_tables:
        st.warning("No output datasets registered in this workflow.")
        return

    selected_table = st.selectbox("Inspect Table:", available_tables, index=len(available_tables) - 1)

    try:
        df_result = context.get_dataframe(selected_table)

        # Show Metrics
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric(label="Total Rows", value=len(df_result))
        col_m2.metric(label="Total Columns", value=len(df_result.columns))
        col_m3.metric(label="Memory Usage", value=f"{df_result.memory_usage(deep=True).sum() / 1024:.2f} KB")

        # Render Interactive Table
        st.dataframe(df_result, use_container_width=True)

        # Download Buttons
        col_csv, col_json = st.columns(2)
        with col_csv:
            st.download_button(
                label="📥 Export CSV",
                data=df_result.to_csv(index=False),
                file_name=f"{selected_table}.csv",
                mime="text/csv",
                use_container_width=True
            )
        with col_json:
            st.download_button(
                label="📥 Export JSON",
                data=df_result.to_json(orient="records", indent=2),
                file_name=f"{selected_table}.json",
                mime="application/json",
                use_container_width=True
            )

    except Exception as e:
        st.error(f"Failed to inspect DuckDB table [{selected_table}]: {str(e)}")