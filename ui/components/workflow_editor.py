import json
from pathlib import Path
import streamlit as st

from config.settings import settings
from core.common.exceptions import WorkflowValidationError
from core.registry.validator import WorkflowValidator


def render_workflow_editor_widget(registry):
    """Visual Workflow Studio & Sample Configurator Widget (Placeholder for Future Canvas Editor)."""
    st.subheader("🛠️ Visual Workflow Studio (Sample)")
    st.caption("Mẫu giao diện cấu hình và tạo mới kịch bản Pipeline ETL trực quan.")

    sample_template = {
        "workflow_id": "sample_inventory_pipeline",
        "description": "Pipeline mẫu tra cứu và tổng hợp tồn kho",
        "inputs": [
            {"name": "category", "label": "Danh Mục Sản Phẩm", "type": "string", "default": "Thời trang"},
            {"name": "status", "label": "Trạng Thái Kho", "type": "string", "default": "IN_STOCK"}
        ],
        "steps": [
            {
                "step_id": "step1_search_products",
                "driver": "nexacro",
                "mode": "batch",
                "method": "POST",
                "endpoint": "http://127.0.0.1:8000/api/nexacro/xml/products/search-list",
                "variables": {
                    "ds_search": {
                        "type": "dataset",
                        "columns": [
                            {"field": "global_input.category", "alias": "category"},
                            {"field": "global_input.status", "alias": "status"}
                        ]
                    }
                },
                "transformations": [],
                "output_dataset": "ds_step1_raw_search",
                "output_config": {
                    "display_title": "Bảng Kết Quả Tìm Kiếm",
                    "columns": [
                        {"field": "product_id", "title": "Mã Sản Phẩm", "visible": True}
                    ]
                }
            }
        ]
    }

    st.markdown("---")

    col_id, col_desc = st.columns([0.4, 0.6])
    with col_id:
        wf_id = st.text_input("Workflow ID:", value=sample_template["workflow_id"], key="editor_wf_id")
    with col_desc:
        wf_desc = st.text_input("Description:", value=sample_template["description"], key="editor_wf_desc")

    st.markdown("##### 📜 Cấu hình Workflow JSON (Schema Inspector)")
    
    json_text = st.text_area(
        "Workflow Configuration JSON:", 
        value=json.dumps(sample_template, indent=2, ensure_ascii=False),
        height=320,
        key="editor_json_area"
    )

    col_val, col_save = st.columns(2)

    with col_val:
        if st.button("🔍 Validate JSON Schema", use_container_width=True):
            try:
                parsed_dict = json.loads(json_text)
                WorkflowValidator.validate_dict(parsed_dict)
                st.success("✅ Workflow Schema hoàn toàn hợp lệ (100% Valid)!")
            except Exception as e:
                st.error(f"❌ Lỗi Validate Schema: {str(e)}")

    with col_save:
        if st.button("💾 Save Workflow JSON", type="primary", use_container_width=True):
            try:
                parsed_dict = json.loads(json_text)
                validated_config = WorkflowValidator.validate_dict(parsed_dict)
                
                target_file = Path(settings.WORKFLOWS_DIR) / f"{wf_id}.json"
                target_file.parent.mkdir(parents=True, exist_ok=True)

                with open(target_file, "w", encoding="utf-8") as f:
                    json.dump(parsed_dict, f, indent=2, ensure_ascii=False)

                st.success(f"🎉 Đã lưu kịch bản `{validated_config.workflow_id}` thành công vào `{target_file}`!")
                if hasattr(registry, "_scan_and_load_workflows"):
                    registry._scan_and_load_workflows()
            except Exception as e:
                st.error(f"❌ Lỗi khi lưu kịch bản: {str(e)}")