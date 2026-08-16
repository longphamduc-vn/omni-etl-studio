import streamlit as st
from core.storage.context import PipelineContext


def render_duckdb_explorer_widget():
    """Renders the DuckDB Inspector with structured table categories and SQL Query Lab."""
    st.subheader("🦆 DuckDB Data Explorer & SQL Query Lab")
    st.caption("Inspect persistent historical storage and step execution outputs.")

    # 1. Connect to DuckDB storage
    context = st.session_state.get("last_context") or PipelineContext(pipeline_id="explorer_session")

    col_info, col_clean = st.columns([0.7, 0.3])
    with col_info:
        st.markdown(f"**Persistent Storage Schema:** `{context.shared_schema}`")
        if context.schema_name and context.schema_name != "ns_explorer_session":
            st.caption(f"Active Execution Schema: `{context.schema_name}`")

    with col_clean:
        if st.button("🧹 Clean Temp Schemas", use_container_width=True):
            context.clean_temporary_schemas()
            st.success("Successfully cleaned temporary execution schemas!")
            st.rerun()

    # 2. Query and categorize tables (Exclude internal _raw tables)
    try:
        tables_df = context.execute_sql(f"""
            SELECT table_schema, table_name 
            FROM information_schema.tables 
            WHERE table_schema IN ('{context.shared_schema}', '{context.schema_name}')
              AND table_name NOT LIKE '%_raw'
            ORDER BY table_schema DESC, table_name ASC;
        """)
        
        shared_tables = []
        step_tables = []
        table_mapping = {}

        if not tables_df.empty:
            for _, r in tables_df.iterrows():
                full_name = f"{r['table_schema']}.{r['table_name']}"
                if r['table_schema'] == context.shared_schema:
                    display_label = f"📁 [PERSISTENT HISTORY] {r['table_name']}"
                    shared_tables.append(display_label)
                else:
                    display_label = f"⚡ [STEP OUTPUT] {r['table_name']}"
                    step_tables.append(display_label)
                
                table_mapping[display_label] = full_name

        all_options = shared_tables + step_tables
    except Exception:
        all_options = []
        table_mapping = {}

    tab_tables, tab_sql = st.tabs(["📋 Registered Tables Viewer", "💻 SQL Console Lab"])

    # TAB 1: BROWSE TABLES
    with tab_tables:
        if all_options:
            selected_label = st.selectbox("Select DuckDB Table to View:", options=all_options)
            selected_full_table = table_mapping.get(selected_label)
            
            if selected_full_table:
                count_df = context.execute_sql(f"SELECT COUNT(*) AS total_rows FROM {selected_full_table};")
                total_rows = count_df["total_rows"].iloc[0] if not count_df.empty else 0

                c_m1, c_m2 = st.columns(2)
                c_m1.metric("Total Rows", f"{total_rows:,}")
                
                df_preview = context.execute_sql(f"SELECT * FROM {selected_full_table} LIMIT 100;")
                c_m2.metric("Total Columns", len(df_preview.columns))

                st.dataframe(df_preview, use_container_width=True)
                if total_rows > 100:
                    st.caption("*(Displaying top 100 rows)*")

                st.download_button(
                    label=f"📥 Download Full CSV [{selected_full_table}.csv]",
                    data=context.execute_sql(f"SELECT * FROM {selected_full_table};").to_csv(index=False),
                    file_name=f"{selected_full_table.replace('.', '_')}.csv",
                    mime="text/csv",
                    key=f"dl_duckdb_{selected_full_table}"
                )
        else:
            st.info("No tables currently present in DuckDB storage.")

    # TAB 2: SQL CONSOLE LAB
    with tab_sql:
        st.markdown("##### Run Ad-hoc SQL Query against DuckDB Engine")
        first_table = list(table_mapping.values())[0] if table_mapping else "shared_storage.ds_historical_products_v2"
        sample_sql = f"SELECT * FROM {first_table} LIMIT 10;"
        
        sql_input = st.text_area("SQL Query Statement:", value=sample_sql, height=120)

        if st.button("▶ Run SQL Query", type="primary"):
            try:
                res_df = context.execute_sql(sql_input)
                st.success(f"Execution successful! Returned {len(res_df)} rows.")
                st.dataframe(res_df, use_container_width=True)
            except Exception as e:
                st.error(f"❌ SQL Execution Error: {str(e)}")