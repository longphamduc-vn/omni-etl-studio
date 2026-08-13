import pytest
import pandas as pd
from pathlib import Path

from config.settings import settings
from core.registry.workflow_registry import WorkflowRegistry
from core.engine.runner import PipelineRunner
from tests.mocks.nexacro_mock_server import MockNexacroServer


@pytest.fixture(scope="module")
def mock_server():
    """Starts the background HTTP Nexacro mock server for E2E integration tests."""
    server = MockNexacroServer(host="127.0.0.1", port=8088)
    server.start()
    yield server
    server.stop()


@pytest.fixture
def workflow_registry():
    """Provides a WorkflowRegistry instance pointing to the workflows/ directory."""
    return WorkflowRegistry()


def test_academic_student_score_chained_e2e(mock_server, workflow_registry):
    """End-to-End Integration Test for 'academic_student_score_chained' workflow:
    1. Step 1 (batch): Fetches students -> filters for status=='ACTIVE' (excludes Bob Jones).
    2. Step 2 (chained_loop): Iterates over active students (STU_001, STU_003) ->
       fetches scores -> filters out score < 50 (excludes score 42 for STU_003) ->
       applies DuckDB deduplication.
    """
    # 1. Fetch workflow config
    workflow_config = workflow_registry.get_workflow("academic_student_score_chained")
    
    # 2. Instantiate and run pipeline
    runner = PipelineRunner(workflow=workflow_config, pipeline_id="e2e_test_academic")
    global_input = {"dept_code": "CS"}
    
    context = runner.run(global_input=global_input)

    try:
        # 3. Verify Step 1 Output Dataset ('active_students')
        step1_df = context.get_dataframe("active_students")
        assert not step1_df.empty
        assert len(step1_df) == 2  # STU_001 (Alice) and STU_003 (Charlie), STU_002 filtered out
        assert set(step1_df["student_id"]) == {"STU_001", "STU_003"}
        assert "INACTIVE" not in step1_df["status"].values

        # 4. Verify Step 2 Output Dataset ('passed_student_scores')
        step2_df = context.get_dataframe("passed_student_scores")
        assert not step2_df.empty
        
        # Expected scores after filter (score >= 50):
        # STU_001: CS101 (95), CS102 (88)
        # STU_003: CS102 (78)  [CS101 (42) filtered out]
        assert len(step2_df) == 3
        
        # Ensure all scores in dataset are >= 50
        assert (step2_df["score"].astype(int) >= 50).all()
        
        # Ensure STU_003 only has CS102 subject present
        stu003_subjects = step2_df[step2_df["student_id"] == "STU_003"]["subject_code"].tolist()
        assert stu003_subjects == ["CS102"]

    finally:
        # Cleanup isolated DuckDB schema namespace
        context.close()


def test_inventory_batch_sync_e2e(mock_server, workflow_registry):
    """End-to-End Integration Test for 'inventory_batch_sync' workflow:
    1. Step 1 (batch): Fetches inventory dataset -> applies DuckDB 'group_by' operator 
       summing quantities by category.
    """
    workflow_config = workflow_registry.get_workflow("inventory_batch_sync")
    
    runner = PipelineRunner(workflow=workflow_config, pipeline_id="e2e_test_inventory")
    global_input = {"warehouse_id": "WH-01"}
    
    context = runner.run(global_input=global_input)

    try:
        summary_df = context.get_dataframe("category_inventory_summary")
        assert not summary_df.empty
        assert len(summary_df) == 2  # Electronics, Furniture

        # Verify SQL aggregation math:
        # Electronics: ITM_01 (10) + ITM_02 (15) = 25
        # Furniture: ITM_03 (5) = 5
        electronics_qty = summary_df[summary_df["category"] == "Electronics"]["quantity_sum"].iloc[0]
        furniture_qty = summary_df[summary_df["category"] == "Furniture"]["quantity_sum"].iloc[0]

        assert float(electronics_qty) == 25.0
        assert float(furniture_qty) == 5.0

    finally:
        context.close()