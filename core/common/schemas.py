# Filepath: core/common/schemas.py
# Updated_at: 2026-08-16 23:15:00
# Description: Full Pydantic schemas for steps, retries, routing, execution states, and workflows.

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ExecutionStatus(str, Enum):
    """Execution status for workflows and steps."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PAUSED = "paused"
    SKIPPED = "skipped"


class RetryConfig(BaseModel):
    """Configuration for automatic step execution retries."""

    max_retries: int = Field(default=3, description="Maximum retry attempts")
    delay_sec: int = Field(default=2, description="Delay between retries in seconds")


class ErrorHandling(BaseModel):
    """Configuration for handling business and execution errors."""

    code_field: str = Field(default="errcode", description="Payload error code key")
    msg_field: str = Field(default="errmsg", description="Payload error message key")
    on_error: str = Field(
        default="pause_for_manual",
        description="Strategy: pause_for_manual, skip_row, continue, fail",
    )


class StepRouting(BaseModel):
    """Routing rule configuration for step branching."""

    next_step: Optional[str] = Field(default=None, description="Explicit next step ID")
    condition: Optional[str] = Field(
        default=None, description="DuckDB SQL expression returning boolean"
    )


class TransformRule(BaseModel):
    """Single transformation operator specification."""

    operator: str = Field(description="Operator name: sql_transform, accumulate_data")
    params: Dict[str, Any] = Field(
        default_factory=dict, description="Operator execution parameters"
    )


class StepConfig(BaseModel):
    """Pipeline execution step definition."""

    step_id: str = Field(description="Unique identifier for the step")
    driver: str = Field(default="passthrough", description="Protocol driver type")
    mode: str = Field(default="batch", description="Execution mode: batch, chained_loop")
    endpoint: Optional[str] = Field(default=None, description="API endpoint URL")
    inputs: List[str] = Field(
        default_factory=list, description="Input dataset IDs for DAG routing"
    )
    variables: Dict[str, Any] = Field(
        default_factory=dict, description="Variable mappings"
    )
    transformations: List[TransformRule] = Field(
        default_factory=list, description="Transformation sequence"
    )
    retry_config: Optional[RetryConfig] = Field(
        default=None, description="Retry configuration"
    )
    error_handling: Optional[ErrorHandling] = Field(
        default=None, description="Error handling strategy"
    )
    routing: Optional[StepRouting] = Field(
        default=None, description="Branching routing rule"
    )
    output_dataset: str = Field(description="Output DuckDB table name")
    output_config: Optional[Dict[str, Any]] = Field(
        default=None, description="UI presentation and column format config"
    )




class TableColumnDefinition(BaseModel):
    """Definition for a single column inside a table input parameter."""

    name: str = Field(description="Column field name")
    label: Optional[str] = Field(default="", description="Column display label")
    type: str = Field(default="string", description="Column data type")
    default: Optional[Any] = Field(default=None, description="Column default value")


class InputDefinition(BaseModel):
    """Definition for a workflow-level input parameter."""

    name: str = Field(description="Variable name")
    label: Optional[str] = Field(default="", description="Display label for UI")
    type: str = Field(default="string", description="Data type: string, integer, boolean, json, table")
    required: bool = Field(default=True, description="Whether the input is mandatory")
    default: Optional[Any] = Field(default=None, description="Default value if not provided")
    description: Optional[str] = Field(default="", description="Parameter description")
    columns: Optional[List[TableColumnDefinition]] = Field(
        default_factory=list, description="Nested column definitions for table type inputs"
    )

class WorkflowConfig(BaseModel):
    """Complete workflow specification model."""

    workflow_id: str = Field(description="Unique workflow identifier")
    workflow_name: Optional[str] = Field(
        default="", description="Human-readable workflow display name"
    )
    domain_path: Optional[str] = Field(
        default="", description="Domain path derived automatically from directory"
    )
    workflow_type: str = Field(default="business", description="Type: business, init")
    description: Optional[str] = Field(default="", description="Workflow overview")
    inputs: List[InputDefinition] = Field(
        default_factory=list, description="Global input definitions"
    )
    steps: List[StepConfig] = Field(
        default_factory=list, description="Sequential step pipeline"
    )


class StepExecutionState(BaseModel):
    """Runtime execution state for an individual step."""

    step_id: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    error_message: Optional[str] = None
    rows_processed: int = 0


class WorkflowExecutionState(BaseModel):
    """Runtime state for an entire workflow run."""

    run_id: str
    workflow_id: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    current_step: Optional[str] = None
    step_states: Dict[str, StepExecutionState] = Field(default_factory=dict)
    created_at: str
    updated_at: str