#!/usr/bin/env bash

# ==============================================================================
# Script Name: update_project.sh
# Description: Tự động dọn dẹp file cũ, tái cấu trúc dự án OmniETL và khởi tạo
#              header chuẩn hóa theo PEP 8 và mốc thời gian hệ thống.
# ==============================================================================

set -e

TIMESTAMP="2026-08-16 17:10:56"

echo "🚀 Bắt đầu quá trình dọn dẹp và nâng cấp cấu trúc dự án OmniETL..."

# 1. XÓA CÁC FILE RÁC VÀ FILE OPERATOR PHÂN MẢNH CŨ
echo "🧹 [1/4] Xóa file rác và các Operator DuckDB cũ..."
rm -f ./all_code.py
rm -f ./core/engine/filter.py
rm -f ./core/engine/operators/duckdb/reshape.py
rm -f ./core/engine/operators/duckdb/aggregate.py
rm -f ./core/engine/operators/duckdb/enrichment.py
rm -f ./core/engine/operators/duckdb/cleaning.py
rm -f ./core/engine/operators/duckdb/join.py

# 2. TẠO CẤU TRÚC THƯ MỤC MỚI (DOMAIN HIERARCHY & LIFECYCLE)
echo "📁 [2/4] Khởi tạo hệ thống thư mục chuẩn hóa..."
mkdir -p ./config
mkdir -p ./core/common
mkdir -p ./core/storage
mkdir -p ./core/engine/operators/python
mkdir -p ./core/engine/operators/duckdb
mkdir -p ./core/lifecycle
mkdir -p ./core/registry
mkdir -p ./drivers
mkdir -p ./workflows/ems/item
mkdir -p ./workflows/ems/po_remain
mkdir -p ./workflows/lifecycle
mkdir -p ./ui/components
mkdir -p ./mock-server

# 3. HÀM TẠO FILE PYTHON VỚI HEADER TIÊU CHUẨN
create_py_file() {
    local filepath="$1"
    local description="$2"
    
    mkdir -p "$(dirname "$filepath")"
    cat <<EOF > "$filepath"
# ==============================================================================
# Filepath: ${filepath}
# Updated_at: ${TIMESTAMP}
# Description: ${description}
# ==============================================================================

EOF
    echo "  + Created: ${filepath}"
}

# 4. KHIẾN TẠO CÁC FILE MỚI VỚI HEADER ĐẦU TRANG
echo "📝 [3/4] Tạo các file cốt lõi với Header chuẩn..."

create_py_file "./config/settings.py" "Cấu hình môi trường ứng dụng (PEP 8)"
create_py_file "./core/common/schemas.py" "Pydantic Models cho Step, RetryConfig, ErrorHandling & Routing"
create_py_file "./core/common/exceptions.py" "Định nghĩa Exception hệ thống và BusinessError"
create_py_file "./core/storage/context.py" "PipelineContext quản lý Session, Inputs, DuckDB Conn và State"
create_py_file "./core/engine/runner.py" "PipelineRunner thực thi DAG Routing, Pause/Resume & Error Handling"
create_py_file "./core/engine/resolver.py" "Jinja2 SQL Templating & Variable Resolver"
create_py_file "./core/engine/evaluator.py" "Đánh giá biểu thức điều kiện trực tiếp trên DuckDB"
create_py_file "./core/engine/transformer.py" "Điều phối Core Operators"
create_py_file "./core/engine/operators/duckdb/transform.py" "SqlTransformOperator vạn năng (thay thế 5 file cũ)"
create_py_file "./core/engine/operators/duckdb/accumulate.py" "AccumulateDataOperator dùng Native QUALIFY"
create_py_file "./core/lifecycle/init_handler.py" "Xử lý sự kiện Lifecycle (ON_APP_INIT, ON_MENU_CLICK)"
create_py_file "./core/registry/workflow_registry.py" "Quản lý Workflow Phân Cấp Domain (Tree View)"
create_py_file "./drivers/base.py" "BaseDriver kiểm tra HTTP Status và Business Payload errcode"
create_py_file "./drivers/nexacro.py" "Nexacro Protocol Driver"
create_py_file "./drivers/rest.py" "Standard REST API Driver"
create_py_file "./drivers/excel_ingest.py" "Chuẩn hóa file Excel chưa quy chuẩn bằng DuckDB"
create_py_file "./ui/app.py" "Streamlit App Main tích hợp Tree View & URL Routing"
create_py_file "./ui/components/execution_runner.py" "UI Runner hỗ trợ Manual Retry & Presentation View"

# 5. TẠO TỆP __init__.py RỖNG NẾU CHƯA CÓ
find . -type d \( -path "./core*" -o -path "./drivers*" -o -path "./config*" -o -path "./ui*" \) -exec touch {}/__init__.py \;

echo "✅ [4/4] Nâng cấp cấu trúc dự án hoàn tất thành công!"