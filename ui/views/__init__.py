# Filepath: ui/views/__init__.py
# Updated_at: 2026-08-16 20:51:00
# Description: UI Views package re-exports for main workspace tabs.

from ui.views.converter_view import render_converter_tab
from ui.views.duckdb_view import render_duckdb_tab
from ui.views.editor_view import render_editor_tab
from ui.views.execution_view import render_execution_tab

__all__ = [
    "render_execution_tab",
    "render_editor_tab",
    "render_duckdb_tab",
    "render_converter_tab",
]