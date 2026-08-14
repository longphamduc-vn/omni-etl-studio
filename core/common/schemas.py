from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ColumnConfig(BaseModel):
    """Schema definition for table input columns."""
    name: str = Field(..., description="Unique column field identifier")
    label: Optional[str] = Field(None, description="Human-readable label for UI rendering")
    type: str = Field(default="string", description="Data type: string, number, boolean")
    default: Optional[Any] = Field(None, description="Default initial value")


class WorkflowInput(BaseModel):
    """Schema definition for dynamic user inputs submitted via UI or API."""
    name: str = Field(..., description="Unique input variable key name")
    label: Optional[str] = Field(None, description="Human-readable label for UI rendering")
    type: str = Field(default="string", description="UI control type: string, number, select, boolean, table")
    default: Optional[Any] = Field(None, description="Default initial value")
    options: Optional[List[Any]] = Field(default=None, description="Options list if input type is select")
    columns: Optional[List[ColumnConfig]] = Field(default=None, description="Column definitions if input type is table")
    description: Optional[str] = Field(None, description="Tooltip or contextual help text")


class VariableConfig(BaseModel):
    """Configuration for mapping execution context variables via JSONPath or static fallback."""
    jsonpath: Optional[str] = Field(None, description="JSONPath query expression to extract value from context")
    default: Optional[Any] = Field(None, description="Fallback static default value if JSONPath evaluation is null")


# Backward compatibility alias for legacy modules
VariableRule = VariableConfig


class FilterCondition(BaseModel):
    """Schema definition for pre-call or post-fetch row filtering logic."""
    field: str = Field(..., description="Target dataset column name")
    operator: str = Field(..., description="Filter comparison operator (e.g., eq, in, gt, contains)")
    value: Any = Field(..., description="Expected value to compare against")


class TransformRule(BaseModel):
    """Schema definition for DuckDB pipeline transformation operators."""
    operator: str = Field(..., description="Transformation operator name (e.g., handle_nulls, deduplicate, group_by)")
    params: Dict[str, Any] = Field(default_factory=dict, description="Operator execution parameters")


class StepConfig(BaseModel):
    """Schema definition for an individual pipeline step execution stage."""
    step_id: str = Field(..., description="Unique step identifier")
    driver: str = Field(..., description="Protocol driver identifier (e.g., nexacro, rest, passthrough)")
    mode: str = Field(default="batch", description="Execution mode: batch or chained_loop")
    method: str = Field(default="POST", description="HTTP/RPC protocol method (e.g., GET, POST, PUT, DELETE)")
    endpoint: str = Field(default="", description="Target HTTP or RPC API endpoint URL")
    variables: Dict[str, VariableConfig] = Field(default_factory=dict, description="Variable resolution rules")
    filters: List[FilterCondition] = Field(default_factory=list, description="List of dataset row filters")
    transformations: List[TransformRule] = Field(default_factory=list, description="Ordered list of DuckDB transformation rules")
    output_dataset: str = Field(..., description="Target DuckDB table name to store step results")
    loop_source: Optional[str] = Field(None, description="Source table name for chained_loop execution mode")
    loop_param_mapping: Optional[Dict[str, str]] = Field(None, description="Field mapping rules for looping step context")


class WorkflowConfig(BaseModel):
    """Declarative workflow execution pipeline schema definition."""
    workflow_id: str = Field(..., description="Unique workflow catalog identifier")
    description: Optional[str] = Field(None, description="Detailed pipeline summary and execution flow overview")
    inputs: List[WorkflowInput] = Field(default_factory=list, description="Declarative input parameter schemas")
    steps: List[StepConfig] = Field(..., description="Sequential list of execution steps")