from typing import Any, Dict, Optional
from uuid import uuid4
import pandas as pd

from core.common.exceptions import OmniETLException
from core.common.logger import log
from core.common.schemas import StepConfig, WorkflowConfig
from core.engine.filter import FilterEngine
from core.engine.resolver import VariableResolver
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
        
        # Binds global inputs directly into context storage for downstream Operators
        self.context.inputs = global_input or {}
        
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

    def _apply_output_config_projection(self, step: StepConfig) -> None:
        """Projects, filters, and reorders DuckDB table columns according to step.output_config strictly."""
        # 1. Ép kiểu output_config về dict an toàn kể cả khi là Pydantic Model
        output_config = step.output_config
        if hasattr(output_config, "model_dump"):
            output_config = output_config.model_dump()
        elif not isinstance(output_config, dict):
            output_config = {}

        columns_config = output_config.get("columns", [])

        if not columns_config:
            log.info(f"[SQL PROJECT SKIPPED] No columns_config defined for step [{step.step_id}]")
            return

        full_table = f"{self.context.schema_name}.{step.output_dataset}"
        
        # 2. Lấy danh sách cột hiện có trong bảng DuckDB
        try:
            check_df = self.context.execute_sql(f"SELECT * FROM {full_table} LIMIT 0;")
            existing_cols = check_df.columns.tolist()
        except Exception as e:
            log.warning(f"[SQL PROJECT SKIPPED] Table '{full_table}' does not exist: {str(e)}")
            return

        # 3. Lọc & Sắp xếp các cột hiển thị theo đúng thứ tự khai báo trong JSON
        select_exprs = []
        for c in columns_config:
            field = c.get("field")
            is_visible = c.get("visible", True)
            
            # Chỉ lấy các cột visible và có tồn tại trong bảng DuckDB
            if is_visible and field in existing_cols:
                select_exprs.append(f'"{field}"')

        if select_exprs:
            sql = f"CREATE OR REPLACE TABLE {full_table} AS SELECT {', '.join(select_exprs)} FROM {full_table};"
            log.info(f"[SQL PROJECT COLUMNS EXECUTE] {sql}")
            self.context.execute_sql(sql)

    def execute_step(self, step: StepConfig, global_context: Dict[str, Any]) -> None:
        """Executes a single pipeline step based on driver type and execution mode."""
        log.info(f"Executing step [{step.step_id}] in mode '{step.mode}' via driver '{step.driver}'")

        # CASE 1: PURE TRANSFORM STEP (PASSTHROUGH / NO API CALL)
        if step.driver in ["passthrough", "none", ""] or not step.endpoint:
            log.info(f"Step [{step.step_id}] is a Pure Transform Step. Skipping API invocation.")
            
            prev_table = step.loop_source or (
                self.workflow.steps[self.workflow.steps.index(step) - 1].output_dataset 
                if self.workflow.steps.index(step) > 0 else ""
            )
            
            if prev_table:
                self.context.execute_sql(
                    f"CREATE OR REPLACE TABLE {self.context.schema_name}.{step.output_dataset} AS "
                    f"SELECT * FROM {self.context.schema_name}.{prev_table};"
                )
                
                if step.transformations:
                    DataTransformer.transform(step.output_dataset, step.transformations, self.context)

            # Áp dụng chuẩn hóa cột trong DuckDB theo output_config
            self._apply_output_config_projection(step)
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

        # Áp dụng chuẩn hóa cột trong DuckDB theo output_config
        self._apply_output_config_projection(step)

    def _execute_batch_step(self, step: StepConfig, driver: Any, global_context: Dict[str, Any]) -> None:
        resolved_vars = VariableResolver.resolve(step.variables or {}, self.context, global_context)
        raw_df = driver.execute(endpoint=step.endpoint, variables=resolved_vars, method=step.method)

        if step.filters and not raw_df.empty:
            raw_df = FilterEngine.apply_filters(raw_df, step.filters)

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
            resolved_vars = VariableResolver.resolve(
                step.variables or {}, self.context, global_context, current_loop_row=row
            )

            res_df = driver.execute(endpoint=step.endpoint, variables=resolved_vars, method=step.method)
            if step.filters and not res_df.empty:
                res_df = FilterEngine.apply_filters(res_df, step.filters)

            if not res_df.empty:
                accumulated_dfs.append(res_df)

        if accumulated_dfs:
            merged_df = pd.concat(accumulated_dfs, ignore_index=True)
        else:
            merged_df = pd.DataFrame(columns=source_df.columns if not source_df.empty else ["status_msg"])

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