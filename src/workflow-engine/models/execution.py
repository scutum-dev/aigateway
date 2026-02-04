"""
Workflow execution tracking models.
"""

from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field


class ExecutionStatus(str, Enum):
    """Workflow execution status."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowStep(BaseModel):
    """A single step in workflow execution."""
    id: Optional[str] = None
    execution_id: str
    node_name: str
    step_order: int
    status: str = "pending"
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    duration_ms: int = 0
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class WorkflowExecution(BaseModel):
    """Complete workflow execution record."""
    id: Optional[str] = None
    workflow_id: Optional[str] = None
    workflow_name: Optional[str] = None
    template_type: Optional[str] = None
    user_id: Optional[str] = None
    team_id: Optional[str] = None
    status: ExecutionStatus = ExecutionStatus.PENDING
    input: Dict[str, Any] = Field(default_factory=dict)
    output: Optional[Dict[str, Any]] = None
    current_node: Optional[str] = None
    error: Optional[str] = None
    total_tokens: int = 0
    total_cost: float = 0.0
    duration_ms: int = 0
    steps: List[WorkflowStep] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        use_enum_values = True


class ExecutionSummary(BaseModel):
    """Summary of an execution for list views."""
    id: str
    workflow_name: Optional[str]
    template_type: Optional[str]
    status: str
    user_id: Optional[str]
    current_node: Optional[str]
    total_cost: float
    duration_ms: int
    created_at: datetime


class CostSummary(BaseModel):
    """Cost summary for workflows."""
    total_executions: int
    total_cost: float
    total_tokens: int
    average_cost_per_execution: float
    cost_by_workflow: Dict[str, float]
    cost_by_user: Dict[str, float]
    cost_by_team: Dict[str, float]
