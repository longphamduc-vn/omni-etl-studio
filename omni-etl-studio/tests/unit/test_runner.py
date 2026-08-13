import pytest
import pandas as pd
from unittest.mock import MagicMock

from core.common.schemas import WorkflowConfig, StepConfig
from core.engine.runner import PipelineRunner


@pytest.fixture
def sample_workflow():
    step1 = StepConfig(
        step_id="step1",
        driver="nexacro",
        mode="batch",
        endpoint="http://mock.endpoint/step1",
        output_dataset="result_step1"
    )
    return WorkflowConfig(workflow_id="unit_test_wf", steps=[step1])


def test_runner_batch_step_execution(sample_workflow):
    mock_driver_instance = MagicMock()
    mock_driver_instance.execute.return_value = pd.DataFrame([
        {"id": 1, "status": "OK"},
        {"id": 2, "status": "OK"}
    ])

    runner = PipelineRunner(workflow=sample_workflow, pipeline_id="unit_runner_test")

    # Override driver resolution to return our mock instance
    runner._get_driver_instance = MagicMock(return_value=mock_driver_instance)

    context = runner.run()

    try:
        res_df = context.get_dataframe("result_step1")
        assert len(res_df) == 2
        assert res_df.iloc[0]["status"] == "OK"
        mock_driver_instance.execute.assert_called_once()
    finally:
        context.close()