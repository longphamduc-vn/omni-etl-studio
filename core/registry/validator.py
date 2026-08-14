import json
from typing import Any, Dict
from core.common.exceptions import WorkflowValidationError
from core.common.logger import log
from core.common.schemas import WorkflowConfig


class WorkflowValidator:
    """Validates pipeline JSON dictionaries or files against Pydantic schema contracts."""

    @staticmethod
    def validate_dict(config_dict: Dict[str, Any]) -> WorkflowConfig:
        """Validates a raw dictionary and parses it into a typed WorkflowConfig model."""
        try:
            workflow_config = WorkflowConfig(**config_dict)
            
            # Semantic checks: ensure step_ids are unique within the workflow
            step_ids = [step.step_id for step in workflow_config.steps]
            if len(step_ids) != len(set(step_ids)):
                raise WorkflowValidationError("Duplicate step_id values detected in workflow steps.")

            log.debug(f"Workflow '{workflow_config.workflow_id}' successfully validated.")
            return workflow_config

        except WorkflowValidationError:
            raise
        except Exception as e:
            raise WorkflowValidationError(f"Workflow validation failure: {str(e)}")

    @classmethod
    def validate_file(cls, file_path: str) -> WorkflowConfig:
        """Loads a JSON file and validates its contents."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls.validate_dict(data)
        except json.JSONDecodeError as jde:
            raise WorkflowValidationError(f"Invalid JSON format in workflow file [{file_path}]: {str(jde)}")
        except Exception as e:
            raise WorkflowValidationError(f"Failed to load workflow file [{file_path}]: {str(e)}")