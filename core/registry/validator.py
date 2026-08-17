# ==============================================================================
# Filepath: core/registry/validator.py
# Updated_at: 2026-08-16 17:35:00
# Description: Validates workflow configuration schemas and DAG step integrity.
# ==============================================================================

from typing import Any, Dict, List, Tuple
from pydantic import ValidationError

from core.common.exceptions import PipelineError
from core.common.logger import log
from core.common.schemas import WorkflowConfig
from drivers.base import DriverRegistry


class WorkflowValidator:
    """Validates workflow configuration rules and DAG step references."""

    @staticmethod
    def validate_schema(raw_cfg: Dict[str, Any]) -> WorkflowConfig:
        """Parses raw JSON dict into WorkflowConfig model and checks Pydantic rules."""
        try:
            return WorkflowConfig(**raw_cfg)
        except ValidationError as ve:
            log.error(f"[VALIDATION ERROR] Workflow schema invalid: {str(ve)}")
            raise PipelineError(f"Invalid workflow configuration schema: {str(ve)}")

    @classmethod
    def validate_workflow(cls, workflow: WorkflowConfig) -> Tuple[bool, List[str]]:
        """Executes deep validation checks across workflow steps and drivers."""
        errors: List[str] = []
        step_ids = set()

        if not workflow.steps:
            errors.append("Workflow must contain at least one execution step.")

        for idx, step in enumerate(workflow.steps):
            # 1. Check duplicate step_id
            if step.step_id in step_ids:
                errors.append(f"Step [{idx}]: Duplicate step_id '{step.step_id}' found.")
            step_ids.add(step.step_id)

            # 2. Check registered driver existence
            if step.driver not in ["passthrough", "none", ""]:
                try:
                    DriverRegistry.get(step.driver)
                except KeyError:
                    errors.append(f"Step [{step.step_id}]: Driver '{step.driver}' is not registered.")

            # 3. Check chained_loop input table declaration
            if step.mode == "chained_loop" and not step.inputs:
                errors.append(f"Step [{step.step_id}]: Mode 'chained_loop' requires 'inputs' declaration.")

            # 4. Validate DAG input dependencies
            for in_dataset in step.inputs:
                if not in_dataset:
                    continue
                # Input can be global or produced by a prior step
                # Warning if input dataset does not match any prior step output
                prior_outputs = {s.output_dataset for s in workflow.steps[:idx]}
                if in_dataset not in prior_outputs and not in_dataset.startswith("ds_"):
                    log.warning(
                        f"[VALIDATION WARNING] Step [{step.step_id}] reads '{in_dataset}' "
                        f"which is not produced by any preceding step."
                    )

        is_valid = len(errors) == 0
        if not is_valid:
            log.error(f"[VALIDATION FAILED] Workflow [{workflow.workflow_id}] failed validation: {errors}")

        return is_valid, errors