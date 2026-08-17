#!/usr/bin/env bash
# Filepath: cleanup_and_init_ui.sh
# Updated_at: 2026-08-16 20:49:10
# Description: Shell script to purge all existing UI files and initialize the new clean UI module structure.

set -e

echo "🧹 Purging existing UI directory..."

# Remove all existing contents inside ./ui directory
rm -rf ./ui/*

echo "📁 Re-creating target UI directories..."

# Create directory structure
mkdir -p ./ui/styles
mkdir -p ./ui/components
mkdir -p ./ui/views

echo "📝 Initializing new UI files with header standard..."

# Function to create file with standard English header
create_file_with_header() {
    local filepath="$1"
    local description="$2"
    local timestamp="2026-08-16 20:49:10"

    cat <<EOF > "$filepath"
# Filepath: ${filepath#./}
# Updated_at: ${timestamp}
# Description: ${description}

EOF
    echo "  + Created: ${filepath}"
}

# 1. UI Root & Styles
create_file_with_header "./ui/__init__.py" "UI package root re-exports."
create_file_with_header "./ui/styles/__init__.py" "UI Styles package re-exports."
create_file_with_header "./ui/styles/theme.py" "Centralized CSS theme injector for dark UI polish."

# 2. UI Components
create_file_with_header "./ui/components/__init__.py" "UI Components package re-exports."
create_file_with_header "./ui/components/sidebar.py" "Sidebar layout component including header, tree navigation, and active state card."
create_file_with_header "./ui/components/tree_navigation.py" "Folder tree navigation component and selection state."
create_file_with_header "./ui/components/url_sync.py" "URL query parameters state manager."
create_file_with_header "./ui/components/workflow_flow.py" "DAG pipeline workflow flow visualization graph."
create_file_with_header "./ui/components/input_builder.py" "Dynamic form input fields builder for workflow parameters."
create_file_with_header "./ui/components/retry_modal.py" "Execution step error handling, skip, and retry control panel."
create_file_with_header "./ui/components/presentation_grid.py" "DataFrame presentation grid and audit output renderer."

# 3. UI Views
create_file_with_header "./ui/views/__init__.py" "UI Views package re-exports for main workspace tabs."
create_file_with_header "./ui/views/execution_view.py" "Pipeline execution console and session lifecycle view."
create_file_with_header "./ui/views/editor_view.py" "Workflow Studio JSON editor view wrapper."
create_file_with_header "./ui/views/duckdb_view.py" "DuckDB data explorer workspace view wrapper."
create_file_with_header "./ui/views/converter_view.py" "Nexacro XML conversion utility workspace view wrapper."

echo "✅ Purge and re-initialization of UI structure completed successfully!"