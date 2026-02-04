"""
Workflow state models for LangGraph integration.
"""

from typing import Optional, List, Dict, Any, Annotated
from datetime import datetime
from operator import add
from pydantic import BaseModel, Field


def merge_messages(left: List[Dict[str, Any]], right: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Custom message merger that works with plain dicts."""
    if not left:
        return right or []
    if not right:
        return left
    return left + right


def merge_dicts(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two dicts, right takes precedence."""
    if not left:
        return right or {}
    if not right:
        return left
    return {**left, **right}


def last_value(left: Any, right: Any) -> Any:
    """Return the last non-None value (for concurrent updates)."""
    return right if right is not None else left


class MessageState(BaseModel):
    """A message in the workflow state."""
    role: str = Field(..., description="Message role: user, assistant, system, tool")
    content: str = Field(..., description="Message content")
    name: Optional[str] = Field(default=None, description="Tool name if tool message")
    tool_call_id: Optional[str] = Field(default=None, description="Tool call ID")
    metadata: Optional[Dict[str, Any]] = None


class NodeState(BaseModel):
    """State of a specific node execution."""
    node_name: str
    status: str = Field(default="pending")  # pending, running, completed, failed
    input: Optional[Dict[str, Any]] = None
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    tokens_used: int = 0
    cost: float = 0.0


class WorkflowState(BaseModel):
    """
    Complete workflow execution state.

    This state is passed through the LangGraph workflow and
    persisted via PostgreSQL checkpointing.
    """
    # Core state - use custom merger instead of LangGraph's add_messages to avoid HumanMessage conversion
    messages: Annotated[List[Dict[str, Any]], merge_messages] = Field(default_factory=list)
    current_node: Annotated[Optional[str], last_value] = None
    execution_id: Optional[str] = None

    # Input/Output
    input: Dict[str, Any] = Field(default_factory=dict)
    output: Annotated[Optional[Dict[str, Any]], last_value] = None

    # Intermediate results (for multi-step workflows) - use merge for concurrent updates
    intermediate_results: Annotated[Dict[str, Any], merge_dicts] = Field(default_factory=dict)

    # Research agent specific - use merge function for concurrent updates
    search_results: Annotated[List[Dict[str, Any]], merge_messages] = Field(default_factory=list)
    analysis: Annotated[Optional[str], last_value] = None

    # Coding agent specific
    code_context: Optional[str] = None
    generated_code: Optional[str] = None
    code_analysis: Optional[str] = None
    iteration_count: int = 0

    # Data analysis specific
    data_query: Optional[str] = None
    query_results: Optional[List[Dict[str, Any]]] = None
    visualization: Optional[Dict[str, Any]] = None

    # Tracking
    node_states: Dict[str, NodeState] = Field(default_factory=dict)
    total_tokens: int = 0
    total_cost: float = 0.0

    # Control flow
    should_continue: bool = True
    error: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True

    def update_node_state(
        self,
        node_name: str,
        status: str,
        tokens: int = 0,
        cost: float = 0.0,
        output: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> "WorkflowState":
        """Update the state of a specific node."""
        now = datetime.utcnow()

        if node_name not in self.node_states:
            self.node_states[node_name] = NodeState(
                node_name=node_name,
                started_at=now
            )

        node_state = self.node_states[node_name]
        node_state.status = status
        node_state.tokens_used += tokens
        node_state.cost += cost

        if output:
            node_state.output = output
        if error:
            node_state.error = error

        if status in ("completed", "failed"):
            node_state.completed_at = now

        # Update totals
        self.total_tokens += tokens
        self.total_cost += cost

        return self
