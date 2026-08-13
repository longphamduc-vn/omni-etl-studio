from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class VariableRule(BaseModel):
    """Rule for variable resolution in VariableEvaluator.
    
    - If `jsonpath` is provided: Evaluates JsonPath against context. `value` acts as fallback if null/missing.
    - If `jsonpath` is None: `value` serves directly as a static literal constant.
    """
    jsonpath: Optional[str] = None
    value: Optional[Any] = None


class FilterCondition(BaseModel):
    """Defines pre-call multi-operator filtering conditions."""
    field: str
    operator: str = Field(..., description="Supported: ==, !=, >, <, >=, <=, IN, NOT IN, CONTAINS")
    value: Union[Any, List[Any]]


class TransformRule(BaseModel):
    """Configuration for data transformation operators."""
    operator: str = Field(..., description="Operator identifier e.g., 'group_by', 'deduplicate', 'handle_nulls'")
    params: Dict[str, Any] = Field(default_factory=dict)


class StepConfig(BaseModel):
    """Declarative specification for a single pipeline step."""
    step_id: str
    driver: str = Field(..., description="Target protocol driver e.g., 'nexacro'")
    mode: str = Field(default="batch", description="Execution mode: 'batch' or 'chained_loop'")
    endpoint: str
    variables: Optional[Dict[str, VariableRule]] = Field(default_factory=dict)
    filters: Optional[List[FilterCondition]] = Field(default_factory=list)
    transformations: Optional[List[TransformRule]] = Field(default_factory=list)
    output_dataset: str = Field(..., description="DuckDB table name to store step results")


class WorkflowConfig(BaseModel):
    """Master workflow pipeline schema."""
    workflow_id: str
    description: Optional[str] = None
    steps: List[StepConfig]