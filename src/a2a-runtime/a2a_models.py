from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# Enums
class AgentStatus(str, Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"


class MessagePriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_HUMAN = "waiting_human"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Pydantic Models
class AgentCapability(BaseModel):
    """Agent capability definition."""

    name: str
    description: str
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None


class Agent(BaseModel):
    """Agent registration."""

    id: str
    name: str
    description: str
    endpoint: str
    capabilities: List[AgentCapability]
    status: AgentStatus = AgentStatus.AVAILABLE
    metadata: Dict[str, Any] = Field(default_factory=dict)
    registered_at: Optional[str] = None
    last_heartbeat: Optional[str] = None


class AgentMessage(BaseModel):
    """Message between agents."""

    id: Optional[str] = None
    source_agent: str
    target_agent: str
    content: Dict[str, Any]
    priority: MessagePriority = MessagePriority.NORMAL
    reply_to: Optional[str] = None
    correlation_id: Optional[str] = None
    created_at: Optional[str] = None


class A2AWorkflowRequest(BaseModel):
    """Request to start an A2A workflow."""

    workflow_type: str  # single_agent, sequential, parallel, supervisor
    agents: List[str]
    input: Dict[str, Any]
    options: Dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = 3600
    require_human_approval: bool = False


class A2AWorkflowResponse(BaseModel):
    """Response from workflow operations."""

    workflow_id: str
    status: WorkflowStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class HumanApprovalRequest(BaseModel):
    """Human approval for workflow step."""

    workflow_id: str
    step_id: str
    approved: bool
    comment: Optional[str] = None
    approver: Optional[str] = None


# Activity Data Classes
@dataclass
class InvokeAgentInput:
    agent_id: str
    capability: str
    input_data: Dict[str, Any]
    timeout_seconds: int = 300


@dataclass
class InvokeAgentOutput:
    success: bool
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    tokens_used: int
    duration_ms: int
