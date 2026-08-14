import json
from pathlib import Path
import streamlit as st

from config.settings import settings
from core.common.exceptions import WorkflowValidationError
from core.registry.validator import WorkflowValidator


def render_variables_builder(step_idx: int, existing_vars: dict) -> dict:
    """Renders a visual Key-Value Mapping table for Step Variables without typing raw JSONPath."""
    st.markdown("##### 🔗 Variables & Data Mapping Builder")
    st.caption("Map request parameters and datasets sent to this step.")

    # Convert existing variables dictionary to internal list representation
    var_items = []
    for k, v in existing_vars.items():
        if isinstance(v, dict) and "jsonpath" in v:
            jp = v["jsonpath"]
            if jp.startswith("$.global_input."):
                src_type = "Global Input"
                src_field = jp.replace("$.global_input.", "")
            elif jp.startswith("$.loop_row"):
                src_type = "Loop Row (Previous Step)"
                src_field = jp.replace("$.loop_row.", "") if len(jp) > 10 else ""
            else:
                src_type = "Custom JSONPath"
                src_field = jp
        else:
            src_type = "Static Value"
            src_field = str(v)
        
        var_items.append({"key": k, "source_type": src_type, "field": src_field})

    num_vars = st.number_input(
        f"Number of mapped variables (Step {step_idx+1}):", 
        min_value=0, 
        max_value=15, 
        value=max(1, len(var_items)),
        key=f"num_vars_{step_idx}"
    )

    result_variables = {}

    for v_idx in range(int(num_vars)):
        item = var_items[v_idx] if v_idx < len(var_items) else {"key": "", "source_type": "Global Input", "field": ""}
        
        c_k, c_src, c_val = st.columns([0.3, 0.35, 0.35])
        
        with c_k:
            v_key = st.text_input(
                "Target Key Name:", 
                value=item["key"], 
                placeholder="e.g. category or ds_id_list", 
                key=f"var_key_{step_idx}_{v_idx}"
            )
        
        with c_src:
            opts = ["Global Input", "Loop Row (Previous Step)", "Static Value", "Custom JSONPath"]
            default_src_idx = opts.index(item["source_type"]) if item["source_type"] in opts else 0
            v_src = st.selectbox(
                "Source Type:", 
                opts,
                index=default_src_idx,
                key=f"var_src_{step_idx}_{v_idx}"
            )

        with c_val:
            v_field = st.text_input(
                "Source Field / Path / Value:", 
                value=item["field"], 
                placeholder="e.g. search_table or Electronics", 
                key=f"var_val_{step_idx}_{v_idx}"
            )

        if v_key.strip():
            if v_src == "Global Input":
                result_variables[v_key.strip()] = {"jsonpath": f"$.global_input.{v_field.strip()}"}
            elif v_src == "Loop Row (Previous Step)":
                if v_field.strip():
                    result_variables[v_key.strip()] = {"jsonpath": f"$.loop_row.{v_field.strip()}"}
                else:
                    result_variables[v_key.strip()] = {"jsonpath": "$.loop_row"}
            elif v_src == "Custom JSONPath":
                result_variables[v_key.strip()] = {"jsonpath": v_field.strip()}
            else:  # Static Value
                result_variables[v_key.strip()] = v_field.strip()

    return result_variables


def render_transformations_builder(step_idx: int, existing_trans: list) -> list:
    """Renders a 100% Visual Form Builder for Data Transformations (No SQL required)."""
    st.markdown("##### 🧪 Transformations Pipeline Builder")
    st.caption("Configure sequential data cleaning, enrichment, and accumulation steps visually.")

    num_trans = st.number_input(
        f"Number of Transformation Steps (Step {step_idx+1}):", 
        min_value=0, 
        max_value=10, 
        value=len(existing_trans),
        key=f"num_trans_{step_idx}"
    )

    result_transformations = []

    for t_idx in range(int(num_trans)):
        trans = existing_trans[t_idx] if t_idx < len(existing_trans) else {}
        
        with st.container(border=True):
            st.caption(f"Transformation Step #{t_idx+1}")
            c_op, c_params = st.columns([0.35, 0.65])
            
            with c_op:
                op_type = st.selectbox(
                    "Select Operator:",
                    ["add_date_column", "accumulate_data", "deduplicate", "handle_nulls", "group_by"],
                    index=["add_date_column", "accumulate_data", "deduplicate", "handle_nulls", "group_by"].index(
                        trans.get("operator", "add_date_column")
                    ) if trans.get("operator") in ["add_date_column", "accumulate_data", "deduplicate", "handle_nulls", "group_by"] else 0,
                    key=f"trans_op_{step_idx}_{t_idx}"
                )

            with c_params:
                params = trans.get("params", {})
                
                # 1. TẠO CỘT NGÀY (VISUAL FORM - NO SQL)
                if op_type == "add_date_column":
                    col1, col2 = st.columns(2)
                    with col1:
                        target_col = st.text_input(
                            "New Date Column Name:", 
                            value=params.get("target_column", "created_date"), 
                            key=f"t_date_col_{step_idx}_{t_idx}"
                        )
                    with col2:
                        date_src = st.selectbox(
                            "Date Source Type:", 
                            ["current_date", "current_timestamp"], 
                            index=0,
                            key=f"t_date_src_{step_idx}_{t_idx}"
                        )
                    
                    result_transformations.append({
                        "operator": "add_date_column",
                        "params": {"target_column": target_col, "date_source": date_src}
                    })

                # 2. TÍCH LŨY VÀO DỮ LIỆU CŨ (ACCUMULATE)
                elif op_type == "accumulate_data":
                    hist_table = st.text_input(
                        "Target Historical Table Name:",
                        value=params.get("target_history_table", "ds_historical_products"),
                        key=f"t_acc_{step_idx}_{t_idx}"
                    )
                    result_transformations.append({
                        "operator": "accumulate_data",
                        "params": {"target_history_table": hist_table, "strategy": "union_by_name"}
                    })

                # 3. LỌC TRÙNG (DEDUPLICATE)
                elif op_type == "deduplicate":
                    col1, col2 = st.columns(2)
                    with col1:
                        subset_str = st.text_input(
                            "Deduplicate Keys (comma separated):",
                            value=", ".join(params.get("subset", ["product_id"])),
                            key=f"t_dedup_{step_idx}_{t_idx}"
                        )
                    with col2:
                        order_col = st.text_input(
                            "Order By Column (Keep Latest):",
                            value=params.get("order_by", "created_date DESC"),
                            key=f"t_ord_{step_idx}_{t_idx}"
                        )
                    
                    subset = [x.strip() for x in subset_str.split(",") if x.strip()]
                    result_transformations.append({
                        "operator": "deduplicate",
                        "params": {"subset": subset, "order_by": order_col}
                    })

                # 4. XỬ LÝ NULL (HANDLE NULLS)
                elif op_type == "handle_nulls":
                    strategy = st.selectbox("Null Strategy:", ["drop", "fill"], key=f"t_strat_{step_idx}_{t_idx}")
                    subset_str = st.text_input("Columns Subset:", value=", ".join(params.get("subset", [])), key=f"t_sub_{step_idx}_{t_idx}")
                    result_transformations.append({"operator": "handle_nulls", "params": {"strategy": strategy, "subset": [x.strip() for x in subset_str.split(",") if x.strip()]}})

                # 5. GOM NHÓM TỔNG HỢP (GROUP BY)
                elif op_type == "group_by":
                    col1, col2 = st.columns(2)
                    with col1:
                        by_str = st.text_input("Group By Columns:", value=", ".join(params.get("by", ["category"])), key=f"t_grp_{step_idx}_{t_idx}")
                    with col2:
                        agg_fn = st.selectbox("Aggregation:", ["COUNT", "SUM", "AVG"], key=f"t_agg_{step_idx}_{t_idx}")
                    
                    result_transformations.append({
                        "operator": "group_by", 
                        "params": {"by": [x.strip() for x in by_str.split(",") if x.strip()], "agg": {"product_id": agg_fn}}
                    })

    return result_transformations

def render_workflow_editor_widget(registry):
    """Visual Form-based Workflow Studio and Configurator."""
    st.subheader("🛠️ Visual Workflow Studio & Builder")
    st.caption("Build, configure, and register ETL workflows visually without typing raw JSON.")

    mode = st.radio("Select Action Mode:", ["✨ Create New Workflow", "✏️ Edit Existing Workflow"], horizontal=True)

    initial_config = {}
    if mode == "✏️ Edit Existing Workflow":
        available_wf = registry.list_workflows()
        if not available_wf:
            st.warning("No existing workflows found.")
            return
        selected_wf_id = st.selectbox("Select Workflow to Load into Visual Builder:", available_wf)
        wf_obj = registry.get_workflow(selected_wf_id)
        initial_config = wf_obj.model_dump()
    else:
        initial_config = {
            "workflow_id": "new_visual_pipeline",
            "description": "Visual form configured pipeline",
            "inputs": [
                {"name": "category", "label": "Product Category", "type": "string", "default": "Electronics"},
                {
                    "name": "search_table",
                    "label": "Search Product ID Table",
                    "type": "table",
                    "columns": [{"name": "product_id", "label": "Product ID", "type": "string"}],
                    "default": [{"product_id": "SP-001"}]
                }
            ],
            "steps": [
                {
                    "step_id": "step1_search_products",
                    "driver": "nexacro",
                    "mode": "batch",
                    "method": "POST",
                    "endpoint": "http://127.0.0.1:8000/api/nexacro/xml/products/search-list",
                    "variables": {
                        "category": {"jsonpath": "$.global_input.category"},
                        "ds_id_list": {"jsonpath": "$.global_input.search_table"}
                    },
                    "transformations": [],
                    "output_dataset": "ds_step1_raw_search"
                }
            ]
        }

    st.markdown("---")

    # ==========================================
    # SECTION 1: PIPELINE METADATA
    # ==========================================
    st.markdown("### 1. 📌 Pipeline Metadata")
    col_m1, col_m2 = st.columns([0.4, 0.6])
    with col_m1:
        wf_id = st.text_input("Workflow ID:", value=initial_config.get("workflow_id", "my_pipeline"))
    with col_m2:
        wf_desc = st.text_input("Description:", value=initial_config.get("description", ""))

    st.markdown("---")

    # ==========================================
    # SECTION 2: INPUT PARAMETERS BUILDER
    # ==========================================
    st.markdown("### 2. 📥 Input Parameters Builder")
    st.caption("Configure dynamic user form inputs or pre-loaded search tables.")

    inputs_list = initial_config.get("inputs", [])
    num_inputs = st.number_input("Number of Global Inputs:", min_value=1, max_value=10, value=max(1, len(inputs_list)))

    configured_inputs = []
    for idx in range(int(num_inputs)):
        inp = inputs_list[idx] if idx < len(inputs_list) else {}
        with st.expander(f"⚙️ Input Field #{idx+1}: `{inp.get('name', 'new_input')}`", expanded=True):
            col_i1, col_i2, col_i3 = st.columns(3)
            with col_i1:
                i_name = st.text_input("Field Key Name:", value=inp.get("name", f"input_{idx+1}"), key=f"inp_name_{idx}")
            with col_i2:
                i_label = st.text_input("UI Display Label:", value=inp.get("label", f"Input {idx+1}"), key=f"inp_label_{idx}")
            with col_i3:
                i_type = st.selectbox("Data Type:", ["string", "table"], index=0 if inp.get("type") == "string" else 1, key=f"inp_type_{idx}")

            if i_type == "string":
                i_default = st.text_input("Default Text Value:", value=str(inp.get("default", "")), key=f"inp_def_{idx}")
                configured_inputs.append({"name": i_name, "label": i_label, "type": "string", "default": i_default})
            else:
                col_name = st.text_input("Table Column Key:", value="product_id", key=f"inp_tbl_col_{idx}")
                configured_inputs.append({
                    "name": i_name,
                    "label": i_label,
                    "type": "table",
                    "columns": [{"name": col_name, "label": col_name.replace("_", " ").title(), "type": "string"}],
                    "default": inp.get("default", [{col_name: "SP-001"}])
                })

    st.markdown("---")

    # ==========================================
    # SECTION 3: PIPELINE STEPS BUILDER
    # ==========================================
    st.markdown("### 3. 🔄 Pipeline Steps Builder")
    
    steps_list = initial_config.get("steps", [])
    num_steps = st.number_input("Number of Steps in Pipeline:", min_value=1, max_value=10, value=max(1, len(steps_list)))

    configured_steps = []
    for idx in range(int(num_steps)):
        step = steps_list[idx] if idx < len(steps_list) else {}
        with st.container(border=True):
            st.markdown(f"#### 📍 Step {idx+1} Configurator")
            
            c_s1, c_s2, c_s3 = st.columns(3)
            with c_s1:
                s_id = st.text_input("Step ID:", value=step.get("step_id", f"step{idx+1}_action"), key=f"s_id_{idx}")
                
                drivers = ["nexacro", "passthrough", "rest"]
                d_idx = drivers.index(step.get("driver")) if step.get("driver") in drivers else 0
                s_driver = st.selectbox("Driver:", drivers, index=d_idx, key=f"s_driver_{idx}")

            with c_s2:
                s_mode = st.selectbox("Execution Mode:", ["batch", "chained_loop"], index=0 if step.get("mode") == "batch" else 1, key=f"s_mode_{idx}")
                s_method = st.selectbox("HTTP Method:", ["POST", "GET"], index=0 if step.get("method") == "POST" else 1, key=f"s_method_{idx}")
            
            with c_s3:
                s_output = st.text_input("Output DuckDB Table:", value=step.get("output_dataset", f"ds_step{idx+1}_output"), key=f"s_out_{idx}")
                s_endpoint = st.text_input("API Endpoint URL:", value=step.get("endpoint", ""), key=f"s_ep_{idx}")

            # Chained Loop Settings
            loop_src, loop_map = None, None
            if s_mode == "chained_loop":
                st.info("🔁 Chained Loop Configuration")
                c_l1, c_l2 = st.columns(2)
                with c_l1:
                    loop_src = st.text_input("Loop Source Dataset:", value=step.get("loop_source", f"ds_step{idx}_output"), key=f"s_lsrc_{idx}")
                with c_l2:
                    loop_map_col = st.text_input("Loop Map Primary Key:", value="product_id", key=f"s_lmap_{idx}")
                    loop_map = {loop_map_col: loop_map_col}

            # Render Visual Variable Builder
            compiled_vars = render_variables_builder(idx, step.get("variables", {}))

            st.markdown("---")

            # Render Visual Transformations Builder
            compiled_trans = render_transformations_builder(idx, step.get("transformations", []))

            step_dict = {
                "step_id": s_id,
                "driver": s_driver,
                "mode": s_mode,
                "method": s_method,
                "endpoint": s_endpoint,
                "variables": compiled_vars,
                "transformations": compiled_trans,
                "output_dataset": s_output
            }
            if s_mode == "chained_loop":
                step_dict["loop_source"] = loop_src
                step_dict["loop_param_mapping"] = loop_map

            configured_steps.append(step_dict)

    # ==========================================
    # SECTION 4: COMPILED JSON PREVIEW & SAVE
    # ==========================================
    st.markdown("---")
    st.markdown("### 4. 🚀 Compiled Workflow Preview & Save")

    compiled_workflow = {
        "workflow_id": wf_id,
        "description": wf_desc,
        "inputs": configured_inputs,
        "steps": configured_steps
    }

    tab_preview, tab_action = st.tabs(["👁️ Compiled JSON Schema Preview", "💾 Save & Register Workflow"])

    with tab_preview:
        st.json(compiled_workflow)

    with tab_action:
        col_act1, col_act2 = st.columns(2)
        with col_act1:
            if st.button("🔍 Validate Generated Schema", use_container_width=True):
                try:
                    WorkflowValidator.validate_dict(compiled_workflow)
                    st.success("✅ Workflow schema is 100% VALID!")
                except WorkflowValidationError as e:
                    st.error(f"❌ Validation Error: {str(e)}")

        with col_act2:
            file_save_name = st.text_input("Save File Name (e.g. inventory/sync.json):", value=f"{wf_id}.json")
            if st.button("💾 Save Workflow JSON", type="primary", use_container_width=True):
                try:
                    validated_config = WorkflowValidator.validate_dict(compiled_workflow)
                    target_path = Path(settings.WORKFLOWS_DIR) / file_save_name
                    target_path.parent.mkdir(parents=True, exist_ok=True)

                    with open(target_path, "w", encoding="utf-8") as f:
                        json.dump(compiled_workflow, f, indent=2, ensure_ascii=False)

                    st.success(f"🎉 Successfully saved workflow `{validated_config.workflow_id}` to `{target_path}`!")
                    registry._scan_and_load_workflows()
                except Exception as e:
                    st.error(f"❌ Failed to save workflow: {str(e)}")