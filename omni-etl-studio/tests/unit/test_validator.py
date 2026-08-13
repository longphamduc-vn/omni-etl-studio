import pytest
from core.registry.validator import WorkflowValidator
from core.common.exceptions import WorkflowValidationError

def test_validate_valid_workflow_dict():
    valid_dict = {
        "workflow_id": "test_wf",
        "description": "Sample workflow",
        "steps": [
            {
                "step_id": "step_1",
                "driver": "nexacro",
                "mode": "batch",
                "endpoint": "http://localhost/api",
                "output_dataset": "ds_out_1"
            }
        ]
    }
    wf_config = WorkflowValidator.validate_dict(valid_dict)
    assert wf_config.workflow_id == "test_wf"
    assert len(wf_config.steps) == 1

def test_validate_duplicate_step_id():
    invalid_dict = {
        "workflow_id": "test_wf_dup",
        "steps": [
            {
                "step_id": "step_same",
                "driver": "nexacro",
                "endpoint": "http://localhost/api1",
                "output_dataset": "ds1"
            },
            {
                "step_id": "step_same",
                "driver": "nexacro",
                "endpoint": "http://localhost/api2",
                "output_dataset": "ds2"
            }
        ]
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        WorkflowValidator.validate_dict(invalid_dict)
    assert "Duplicate step_id" in str(exc_info.value)