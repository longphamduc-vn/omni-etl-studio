from typing import Any, Dict, Optional
import pandas as pd

from core.common.exceptions import OmniETLException
from core.common.logger import log
from core.common.schemas import StepConfig, WorkflowConfig
from core.engine.evaluator import VariableEvaluator
from core.engine.filter import FilterEngine
from core.engine.transformer import DataTransformer
from core.storage.context import PipelineContext
from drivers.base import BaseDriver
from drivers.nexacro import NexacroDriver


class PipelineRunner:
    """Sequencer and execution coordinator for omni-etl-studio pipelines."""

    DRIVER_MAP = {
        "nexacro": NexacroDriver,
    }

    def __init__(self, workflow: WorkflowConfig, pipeline_id: Optional[str] = None):
        self.workflow = workflow
        self.pipeline_id = pipeline_id or workflow.workflow_id
        self.context = PipelineContext(pipeline_id=self.pipeline_id)

    def _get_driver_instance(self, driver_name: str) -> BaseDriver:
        """Instantiates the concrete driver adapter for a target step."""
        driver_cls = self.DRIVER_MAP.get(driver_name.lower())
        if not driver_cls:
            raise OmniETLException(f"Driver '{driver_name}' is not supported by PipelineRunner.")
        return driver_cls()

    def execute_step(self, step: StepConfig, global_context: Dict[str, Any]):
        """Executes a single step under either 'batch' or 'chained_loop' operational mode."""
        log.info(f"Executing step [{step.step_id}] in '{step.mode}' mode via driver '{step.driver}'")

        driver = self._get_driver_instance(step.driver)

        if step.mode == "batch":
            self._execute_batch_step(step, driver, global_context)
        elif step.mode == "chained_loop":
            self._execute_chained_loop_step(step, driver, global_context)
        else:
            raise OmniETLException(f"Unsupported step execution mode: {step.mode}")

    def _execute_batch_step(self, step: StepConfig, driver: BaseDriver, global_context: Dict[str, Any]):
        """Executes a single POST request containing all batch parameters/payloads."""
        # 1. Resolve variables
        resolved_vars = VariableEvaluator.evaluate_all(step.variables or {}, global_context)

        # 2. Execute Driver HTTP Transport & Parse
        raw_df = driver.execute(endpoint=step.endpoint, variables=resolved_vars)

        # 3. Apply Pre-call/Post-parse filtering
        filtered_df = FilterEngine.apply_filters(raw_df, step.filters or [])

        # 4. Save intermediate DataFrame to DuckDB schema
        initial_table = f"{step.step_id}_raw"
        self.context.save_dataframe(initial_table, filtered_df)

        # 5. Apply Transformation rules (DuckDB or Python operators)
        final_table = DataTransformer.transform(initial_table, step.transformations or [], self.context)

        # 6. Store to step output dataset if table name changed
        if final_table != step.output_dataset:
            sql = f"CREATE OR REPLACE TABLE {self.context.schema_name}.{step.output_dataset} AS SELECT * FROM {self.context.schema_name}.{final_table};"
            self.context.execute_sql(sql)

        log.info(f"Completed batch step [{step.step_id}]. Saved output table '{step.output_dataset}'.")

    def _execute_chained_loop_step(self, step: StepConfig, driver: BaseDriver, global_context: Dict[str, Any]):
        """Sequentially executes $N$ requests iterating over rows of an antecedent step result."""
        source_table = step.variables.get("loop_source", {}).value if step.variables.get("loop_source") else None
        if not source_table:
            raise OmniETLException(f"Step [{step.step_id}] in chained_loop mode requires 'loop_source' variable.")

        # Read loop source records from DuckDB context
        source_df = self.context.get_dataframe(source_table)
        if source_df.empty:
            log.warning(f"Loop source table '{source_table}' is empty. Skipping step [{step.step_id}].")
            return

        accumulated_dfs = []

        for idx, row in source_df.iterrows():
            loop_row = row.to_dict()
            loop_context = {**global_context, "loop_row": loop_row, "row": loop_row}

            # Resolve loop variables
            resolved_vars = VariableEvaluator.evaluate_all(step.variables or {}, loop_context)

            # Execute driver for iteration row
            iter_df = driver.execute(endpoint=step.endpoint, variables=resolved_vars)
            if not iter_df.empty:
                accumulated_dfs.append(iter_df)

        # Combine all iteration responses into unified dataset
        combined_df = pd.concat(accumulated_dfs, ignore_index=True) if accumulated_dfs else pd.DataFrame()
        filtered_df = FilterEngine.apply_filters(combined_df, step.filters or [])

        # Save & transform
        initial_table = f"{step.step_id}_raw"
        self.context.save_dataframe(initial_table, filtered_df)
        final_table = DataTransformer.transform(initial_table, step.transformations or [], self.context)

        if final_table != step.output_dataset:
            sql = f"CREATE OR REPLACE TABLE {self.context.schema_name}.{step.output_dataset} AS SELECT * FROM {self.context.schema_name}.{final_table};"
            self.context.execute_sql(sql)

        log.info(f"Completed chained_loop step [{step.step_id}] across {len(source_df)} iterations.")

    def run(self, global_input: Optional[Dict[str, Any]] = None, session: Optional[Dict[str, Any]] = None) -> PipelineContext:
        """Executes the entire workflow pipeline sequentially."""
        global_context = {
            "global_input": global_input or {},
            "session": session or {}
        }

        log.info(f"Starting execution of pipeline '{self.workflow.workflow_id}' (Run ID: {self.pipeline_id})")

        try:
            for step in self.workflow.steps:
                self.execute_step(step, global_context)

            log.info(f"Pipeline '{self.workflow.workflow_id}' executed successfully.")
            return self.context

        except Exception as e:
            log.error(f"Pipeline execution failed: {str(e)}")
            self.context.close()
            raise OmniETLException(f"Pipeline execution failure: {str(e)}")