# ==============================================================================
# Filepath: core/engine/operators/duckdb/__init__.py
# Updated_at: 2026-08-16 18:13:00
# Description: DuckDB operators package exports.
# ==============================================================================

from core.engine.operators.duckdb.transform import SqlTransformOperator
from core.engine.operators.duckdb.accumulate import AccumulateDataOperator

__all__ = [
    "SqlTransformOperator",
    "AccumulateDataOperator",
]