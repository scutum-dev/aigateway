"""
Workflow definition models.
"""

from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field


class WorkflowStatus(str, Enum):
    """Workflow definition status."""
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class WorkflowTemplate(str, Enum):
    """Pre-built workflow templates."""
    RESEARCH = "research"
    CODING = "coding"
    DATA_ANALYSIS = "data_analysis"
    CUSTOM = "custom"


class NodeDefinition(BaseModel):
    """Definition of a workflow node."""
    name: str = Field(..., description="Unique node identifier")
    type: str = Field(..., description="Node type: llm, tool, router, etc.")
    config: Dict[str, Any] = Field(default_factory=dict, description="Node configuration")
    description: Optional[str] = None


class EdgeDefinition(BaseModel):
    """Definition of a workflow edge."""
    source: str = Field(..., description="Source node name")
    target: str = Field(..., description="Target node name")
    condition: Optional[str] = Field(default=None, description="Conditional expression")


class GraphDefinition(BaseModel):
    """Definition of the workflow graph."""
    nodes: List[NodeDefinition] = Field(default_factory=list)
    edges: List[EdgeDefinition] = Field(default_factory=list)
    entry_point: str = Field(..., description="Starting node")
    end_nodes: List[str] = Field(default_factory=list, description="Terminal nodes")


class WorkflowDefinition(BaseModel):
    """Complete workflow definition."""
    id: Optional[str] = None
    name: str = Field(..., description="Workflow name")
    version: str = Field(default="1.0.0", description="Workflow version")
    template_type: WorkflowTemplate = Field(default=WorkflowTemplate.CUSTOM)
    description: Optional[str] = None
    graph_definition: GraphDefinition
    input_schema: Optional[Dict[str, Any]] = Field(default=None, description="JSON Schema for input")
    output_schema: Optional[Dict[str, Any]] = Field(default=None, description="JSON Schema for output")
    is_active: bool = Field(default=True)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        use_enum_values = True


class WorkflowInput(BaseModel):
    """Input for starting a workflow execution."""
    workflow_id: Optional[str] = Field(default=None, description="Workflow definition ID")
    template: Optional[WorkflowTemplate] = Field(default=None, description="Template type if no workflow_id")
    input: Dict[str, Any] = Field(..., description="Input data for the workflow")
    user_id: Optional[str] = None
    team_id: Optional[str] = None
    timeout_seconds: Optional[int] = Field(default=None, description="Execution timeout")


class WorkflowOutput(BaseModel):
    """Output from workflow execution."""
    execution_id: str
    status: str
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    total_cost: Optional[float] = None
    total_tokens: Optional[int] = None
    duration_ms: Optional[int] = None
