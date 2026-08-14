from typing import Any, Dict, Optional
from uuid import uuid4
import pandas as pd

from core.common.exceptions import OmniETLException
from core.common.logger import log
from core.common.schemas import StepConfig, WorkflowConfig
from core.engine.evaluator import VariableEvaluator
from core.engine.filter import FilterEngine
from core.engine.transformer import DataTransformer
from core.storage.context import PipelineContext
from drivers.base import DriverRegistry


class PipelineRunner:
    """Executes a validated WorkflowConfig pipeline step-by-step."""

    def __init__(self, workflow: WorkflowConfig, pipeline_id: Optional[str] = None):
        self.workflow = workflow
        self.pipeline_id = pipeline_id or f"run_{uuid4().hex[:8]}"
        self.context = PipelineContext(pipeline_id=self.pipeline_id)

    def run(self, global_input: Optional[Dict[str, Any]] = None, session: Optional[Dict[str, Any]] = None) -> PipelineContext:
        """Executes the pipeline workflow across all configured steps."""
        global_context = {
            "global_input": global_input or {},
            "session": session or {}
        }

        log.info(f"Starting execution of pipeline '{self.workflow.workflow_id}' (Run ID: {self.pipeline_id})")

        try:
            for step in self.workflow.steps:
                self.execute_step(step, global_context)
            return self.context
        except Exception as e:
            self.context.close()
            raise OmniETLException(f"Pipeline execution failure: {str(e)}")

    def execute_step(self, step: StepConfig, global_context: Dict[str, Any]) -> None:
        """Executes a single pipeline step based on driver type and execution mode."""
        log.info(f"Executing step [{step.step_id}] in mode '{step.mode}' via driver '{step.driver}'")

        # CASE 1: PURE TRANSFORM STEP (PASSTHROUGH / NO API CALL)
        if step.driver in ["passthrough", "none", ""] or not step.endpoint:
            log.info(f"Step [{step.step_id}] is a Pure Transform Step. Skipping API invocation.")
            
            # Determine source input table
            prev_table = step.loop_source or (
                self.workflow.steps[self.workflow.steps.index(step) - 1].output_dataset 
                if self.workflow.steps.index(step) > 0 else ""
            )
            
            if prev_table and step.transformations:
                final_table = DataTransformer.transform(prev_table, step.transformations, self.context)
                if final_table != step.output_dataset:
                    self.context.execute_sql(
                        f"CREATE OR REPLACE TABLE {self.context.schema_name}.{step.output_dataset} AS "
                        f"SELECT * FROM {self.context.schema_name}.{final_table};"
                    )
            return

        # CASE 2: API INVOCATION STEP (BATCH OR CHAINED LOOP)
        driver_cls = DriverRegistry.get(step.driver)
        driver = driver_cls()

        if step.mode == "batch":
            self._execute_batch_step(step, driver, global_context)
        elif step.mode == "chained_loop":
            self._execute_chained_loop_step(step, driver, global_context)
        else:
            raise OmniETLException(f"Unsupported execution mode: {step.mode}")

    def _execute_batch_step(self, step: StepConfig, driver: Any, global_context: Dict[str, Any]) -> None:
        resolved_vars = VariableEvaluator.evaluate_all(step.variables or {}, global_context)
        raw_df = driver.execute(endpoint=step.endpoint, variables=resolved_vars, method=step.method)

        if step.filters and not raw_df.empty:
            raw_df = FilterEngine.apply_filters(raw_df, step.filters)

        # Ensure DataFrame has at least a dummy structure if completely empty
        if raw_df.empty or len(raw_df.columns) == 0:
            raw_df = pd.DataFrame(columns=["status_msg"])

        raw_table_name = f"{step.step_id}_raw"
        self.context.save_dataframe(raw_table_name, raw_df)

        final_table = DataTransformer.transform(raw_table_name, step.transformations or [], self.context)

        if final_table != step.output_dataset:
            self.context.execute_sql(
                f"CREATE OR REPLACE TABLE {self.context.schema_name}.{step.output_dataset} AS "
                f"SELECT * FROM {self.context.schema_name}.{final_table};"
            )

    def _execute_chained_loop_step(self, step: StepConfig, driver: Any, global_context: Dict[str, Any]) -> None:
        if not step.loop_source:
            raise OmniETLException(f"Chained loop step [{step.step_id}] requires 'loop_source'.")

        source_df = self.context.get_dataframe(step.loop_source)
        loop_records = source_df.to_dict(orient="records") if not source_df.empty else []

        accumulated_dfs = []
        for row in loop_records:
            loop_context = {**global_context, "loop_row": row}
            resolved_vars = VariableEvaluator.evaluate_all(step.variables or {}, loop_context)

            res_df = driver.execute(endpoint=step.endpoint, variables=resolved_vars, method=step.method)
            if step.filters and not res_df.empty:
                res_df = FilterEngine.apply_filters(res_df, step.filters)

            if not res_df.empty:
                accumulated_dfs.append(res_df)

        if accumulated_dfs:
            merged_df = pd.concat(accumulated_dfs, ignore_index=True)
        else:
            # Fallback to source DataFrame schema structure if loop produced no results
            merged_df = pd.DataFrame(columns=source_df.columns if not source_df.empty else ["status_msg"])

        # FIX: Ensure DataFrame has at least one valid column for DuckDB table creation
        if len(merged_df.columns) == 0:
            merged_df["status_msg"] = None

        raw_table_name = f"{step.step_id}_raw"
        self.context.save_dataframe(raw_table_name, merged_df)

        final_table = DataTransformer.transform(raw_table_name, step.transformations or [], self.context)

        if final_table != step.output_dataset:
            self.context.execute_sql(
                f"CREATE OR REPLACE TABLE {self.context.schema_name}.{step.output_dataset} AS "
                f"SELECT * FROM {self.context.schema_name}.{final_table};"
            )