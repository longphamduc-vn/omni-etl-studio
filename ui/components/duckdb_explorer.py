import streamlit as st
import pandas as pd


def render_duckdb_explorer_widget():
    """Renders the DuckDB Inspector and Interactive SQL Execution Console."""
    st.subheader("🦆 DuckDB Data Explorer & SQL Query Lab")
    st.caption("Inspect pipeline schemas, DuckDB tables, or execute ad-hoc SQL queries directly.")

    context = st.session_state.get("last_context")

    if not context or not context.conn:
        st.info("ℹ️ No active DuckDB execution pipeline found. Run a workflow first to inspect its DuckDB tables.")
        return

    st.markdown(f"**Active Schema Namespace:** `{context.schema_name}`")

    # Fetch List of Tables in the Current Schema
    try:
        tables_df = context.execute_sql(f"""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = '{context.schema_name}';
        """)
        table_names = tables_df["table_name"].tolist() if not tables_df.empty else []
    except Exception:
        table_names = []

    tab_tables, tab_sql = st.tabs(["📋 Registered Tables Viewer", "💻 SQL Console Lab"])

    # TAB 1: BROWSE TABLES
    with tab_tables:
        if table_names:
            selected_table = st.selectbox("Select DuckDB Table to View:", options=table_names)
            
            if selected_table:
                df_table = context.get_dataframe(selected_table)
                
                col_m1, col_m2 = st.columns(2)
                col_m1.metric("Total Rows", len(df_table))
                col_m2.metric("Total Columns", len(df_table.columns))

                st.dataframe(df_table, use_container_width=True)

                st.download_button(
                    label=f"📥 Download Table [{selected_table}.csv]",
                    data=df_table.to_csv(index=False),
                    file_name=f"{selected_table}.csv",
                    mime="text/csv",
                    key=f"dl_duckdb_{selected_table}"
                )
        else:
            st.warning("No tables currently present in the active schema namespace.")

    # TAB 2: SQL CONSOLE LAB
    with tab_sql:
        st.markdown("##### Run Ad-hoc SQL Query against DuckDB Engine")
        sample_sql = f"SELECT * FROM {context.schema_name}.{table_names[0]} LIMIT 10;" if table_names else "SELECT 1 AS test;"
        
        sql_input = st.text_area("SQL Query Statement:", value=sample_sql, height=120)

        if st.button("▶ Run SQL Query", type="primary"):
            try:
                res_df = context.execute_sql(sql_input)
                st.success(f"Execution successful! Returned {len(res_df)} rows.")
                st.dataframe(res_df, use_container_width=True)
            except Exception as e:
                st.error(f"❌ SQL Execution Error: {str(e)}")