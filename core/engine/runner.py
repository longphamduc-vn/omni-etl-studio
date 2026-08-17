# ==============================================================================
# Filepath: core/engine/runner.py
# Updated_at: 2026-08-16 17:30:00
# Description: Pipeline execution runner supporting generic BusinessError handling.
# ==============================================================================

import time
from typing import Any, Dict, Optional
from uuid import uuid4
import pandas as pd

from core.common.exceptions import BusinessError, PipelineError, RetryError
from core.common.logger import log
from core.common.schemas import StepConfig, WorkflowConfig
from core.engine.evaluator import VariableEvaluator
from core.engine.resolver import VariableResolver
from core.engine.transformer import DataTransformer
from core.storage.context import PipelineContext
from drivers.base import DriverRegistry


class PipelineRunner:
    """Generic pipeline runner decoupling protocol parsing from execution routing."""

    def __init__(self, workflow: WorkflowConfig, pipeline_id: Optional[str] = None):
        self.workflow = workflow
        self.pipeline_id = pipeline_id or f"run_{uuid4().hex[:8]}"
        self.context = PipelineContext(
            pipeline_id=self.pipeline_id,
            domain_path=workflow.domain_path
        )

    def run(
        self,
        input_data: Optional[Dict[str, Any]] = None,
        session: Optional[Dict[str, Any]] = None,
        start_step_id: Optional[str] = None
    ) -> PipelineContext:
        """Executes the pipeline or resumes from a paused step ID."""
        self.context.input_data = input_data or self.context.input_data
        self.context.session = session or self.context.session
        self.context.exec_status = "RUNNING"

        log.info(f"Starting pipeline execution [{self.workflow.workflow_id}] (Run ID: {self.pipeline_id})")

        steps = self.workflow.steps
        start_idx = 0

        # Resume execution from specified step ID if provided (Manual Retry)
        if start_step_id:
            for idx, step in enumerate(steps):
                if step.step_id == start_step_id:
                    start_idx = idx
                    log.info(f"Resuming execution from step [{start_step_id}]")
                    break

        curr_idx = start_idx
        while curr_idx < len(steps):
            step = steps[curr_idx]

            try:
                next_step_id = self.execute_step(step)

                # Pause pipeline execution if a BusinessError triggered PAUSED state
                if self.context.exec_status == "PAUSED_WAITING_RETRY":
                    log.warning(f"Pipeline execution paused at step [{step.step_id}]. Awaiting manual retry.")
                    return self.context

                # Handle dynamic routing
                if next_step_id and next_step_id != "NEXT":
                    if next_step_id == "END":
                        break
                    
                    found_idx = next((i for i, s in enumerate(steps) if s.step_id == next_step_id), None)
                    if found_idx is not None:
                        curr_idx = found_idx
                        continue

                curr_idx += 1

            except Exception as e:
                self.context.exec_status = "FAILED"
                self.context.error_info = {"failed_step": step.step_id, "error": str(e)}
                log.error(f"Pipeline failure at step [{step.step_id}]: {str(e)}")
                raise PipelineError(f"Pipeline execution failure: {str(e)}")

        self.context.exec_status = "SUCCESS"
        return self.context

    def execute_step(self, step: StepConfig) -> Optional[str]:
        """Executes a step delegating driver error inspection to Driver instance."""
        log.info(f"Executing step [{step.step_id}] via driver '{step.driver}'")

        if step.driver in ["passthrough", "none", ""] or not step.endpoint:
            return self._execute_transform_step(step)

        driver_cls = DriverRegistry.get(step.driver)
        driver = driver_cls()

        retry_cfg = step.retry_config
        max_retries = retry_cfg.max_retries if retry_cfg else 1
        delay_sec = retry_cfg.delay_sec if retry_cfg else 0

        for attempt in range(1, max_retries + 1):
            try:
                if step.mode == "batch":
                    self._execute_batch_step(step, driver)
                elif step.mode == "chained_loop":
                    self._execute_chained_loop_step(step, driver)

                # Check SQL routing condition on success
                if step.routing and step.routing.condition:
                    cond_pass = VariableEvaluator.evaluate_condition(step.routing.condition, self.context)
                    if cond_pass and step.routing.next_step:
                        return step.routing.next_step

                return step.routing.next_step if step.routing else None

            except BusinessError as be:
                # Catch generic BusinessError raised by any protocol Driver
                log.error(f"[BUSINESS ERROR] Step [{step.step_id}] (Code: {be.code}): {be.msg}")
                
                err_handling = step.error_handling
                strategy = err_handling.on_error if err_handling else "pause_for_manual"

                if strategy == "pause_for_manual":
                    self.context.exec_status = "PAUSED_WAITING_RETRY"
                    self.context.error_info = {
                        "failed_step": step.step_id,
                        "err_code": be.code,
                        "err_msg": be.msg,
                        "payload": be.payload
                    }
                    return None
                elif strategy in ["skip_row", "continue"]:
                    log.warning(f"Strategy '{strategy}' applied. Bypassing step [{step.step_id}].")
                    return None
                else:
                    raise

            except Exception as e:
                log.warning(f"Attempt {attempt}/{max_retries} failed for step [{step.step_id}]: {str(e)}")
                if attempt < max_retries:
                    time.sleep(delay_sec)
                else:
                    raise RetryError(f"Step [{step.step_id}] exhausted retries: {str(e)}")

        return None

    def _execute_transform_step(self, step: StepConfig) -> Optional[str]:
        prev_table = step.inputs[0] if step.inputs else ""
        full_output = f"{self.context.schema_name}.{step.output_dataset}"

        if prev_table:
            prev_full = f"{self.context.schema_name}.{prev_table}"
            self.context.execute_sql(f"CREATE OR REPLACE TABLE {full_output} AS SELECT * FROM {prev_full};")

        if step.transformations:
            DataTransformer.transform(step.output_dataset, step.transformations, self.context)

        return step.routing.next_step if step.routing else None

    def _execute_batch_step(self, step: StepConfig, driver: Any) -> None:
        vars_res = VariableResolver.resolve(step.variables or {}, self.context)
        
        # Driver executes API AND performs protocol-specific response inspection inside driver.execute()
        raw_df = driver.execute(
            endpoint=step.endpoint,
            variables=vars_res,
            error_cfg=step.error_handling.model_dump() if step.error_handling else None
        )

        if raw_df is None or raw_df.empty:
            raw_df = pd.DataFrame(columns=["status_msg"])

        raw_table = f"{step.step_id}_raw"
        self.context.save_dataframe(raw_table, raw_df)

        final_table = DataTransformer.transform(raw_table, step.transformations or [], self.context)

        full_output = f"{self.context.schema_name}.{step.output_dataset}"
        if final_table != step.output_dataset:
            final_full = f"{self.context.schema_name}.{final_table}"
            self.context.execute_sql(f"CREATE OR REPLACE TABLE {full_output} AS SELECT * FROM {final_full};")

    def _execute_chained_loop_step(self, step: StepConfig, driver: Any) -> None:
        loop_source = step.inputs[0] if step.inputs else ""
        if not loop_source:
            raise PipelineError(f"Chained loop step [{step.step_id}] requires at least one input in 'inputs'.")

        source_df = self.context.get_dataframe(loop_source)
        loop_records = source_df.to_dict(orient="records") if source_df is not None and not source_df.empty else []

        accum_dfs = []
        for row in loop_records:
            vars_res = VariableResolver.resolve(step.variables or {}, self.context, loop_row=row)
            res_df = driver.execute(
                endpoint=step.endpoint,
                variables=vars_res,
                error_cfg=step.error_handling.model_dump() if step.error_handling else None
            )

            if res_df is not None and not res_df.empty:
                accum_dfs.append(res_df)

        if accum_dfs:
            merged_df = pd.concat(accum_dfs, ignore_index=True)
        else:
            merged_df = pd.DataFrame(columns=source_df.columns if source_df is not None else ["status_msg"])

        raw_table = f"{step.step_id}_raw"
        self.context.save_dataframe(raw_table, merged_df)

        final_table = DataTransformer.transform(raw_table, step.transformations or [], self.context)

        full_output = f"{self.context.schema_name}.{step.output_dataset}"
        if final_table != step.output_dataset:
            final_full = f"{self.context.schema_name}.{final_table}"
            self.context.execute_sql(f"CREATE OR REPLACE TABLE {full_output} AS SELECT * FROM {final_full};")