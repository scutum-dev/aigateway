"""
Pydantic models for Policy Router service.
"""

from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class GatewayCapability(str, Enum):
    """Model capabilities for routing decisions."""
    STREAMING = "streaming"
    FUNCTION_CALLING = "function_calling"
    VISION = "vision"
    JSON_MODE = "json_mode"
    TOOL_USE = "tool_use"


class ModelTier(str, Enum):
    """Model pricing tiers."""
    FREE = "free"
    BUDGET = "budget"
    STANDARD = "standard"
    PREMIUM = "premium"


class RoutingRequest(BaseModel):
    """Request for model routing decision."""
    user_id: Optional[str] = Field(default=None, description="User identifier")
    team_id: Optional[str] = Field(default=None, description="Team identifier")
    requested_model: Optional[str] = Field(default=None, description="Requested model alias or name")
    budget_remaining: Optional[float] = Field(default=None, description="Remaining budget in USD")
    latency_sla_ms: Optional[int] = Field(default=None, description="Maximum acceptable latency in ms")
    required_capabilities: Optional[List[str]] = Field(default=None, description="Required model capabilities")
    messages: Optional[List[Dict[str, Any]]] = Field(default=None, description="Messages for context estimation")
    max_tokens: Optional[int] = Field(default=None, description="Maximum output tokens")
    priority: Optional[str] = Field(default="normal", description="Request priority: low, normal, high")


class ModelInfo(BaseModel):
    """Model information with current metrics."""
    model_id: str
    provider: str
    tier: ModelTier
    cost_per_1k_input: Decimal
    cost_per_1k_output: Decimal
    supports_streaming: bool = True
    supports_function_calling: bool = False
    supports_vision: bool = False
    default_latency_sla_ms: int = 5000
    # Current metrics (from Prometheus)
    current_latency_ms: Optional[float] = None
    current_error_rate: Optional[float] = None
    requests_per_minute: Optional[int] = None
    is_available: bool = True


class RoutingDecision(BaseModel):
    """Response with routing decision."""
    selected_model: str = Field(..., description="Selected model for the request")
    fallback_models: List[str] = Field(default_factory=list, description="Ordered list of fallback models")
    decision_reason: str = Field(..., description="Explanation for the routing decision")
    estimated_cost: Optional[float] = Field(default=None, description="Estimated cost for the request")
    estimated_latency_ms: Optional[int] = Field(default=None, description="Estimated latency")
    policy_evaluations: Optional[List[Dict[str, Any]]] = Field(default=None, description="Policy evaluation details")


class PolicyEvaluationRequest(BaseModel):
    """Request for direct Cedar policy evaluation."""
    principal: str = Field(..., description="Principal entity (user::user-id)")
    action: str = Field(..., description="Action being evaluated")
    resource: str = Field(..., description="Resource entity (model::gpt-4o)")
    context: Dict[str, Any] = Field(default_factory=dict, description="Context for policy evaluation")


class PolicyEvaluationResponse(BaseModel):
    """Response from Cedar policy evaluation."""
    decision: str = Field(..., description="allow, deny, or error")
    reasons: List[str] = Field(default_factory=list, description="Policy IDs that contributed to decision")
    errors: List[str] = Field(default_factory=list, description="Any errors during evaluation")


class RoutingDecisionRecord(BaseModel):
    """Database record for routing decisions."""
    id: Optional[str] = None
    timestamp: datetime
    user_id: Optional[str] = None
    team_id: Optional[str] = None
    requested_model: Optional[str] = None
    selected_model: str
    fallback_models: List[str]
    decision_reason: str
    context_snapshot: Dict[str, Any]


class ModelRoutingConfig(BaseModel):
    """Configuration for a model in routing."""
    model_id: str
    provider: str
    tier: str
    cost_per_1k_input: Decimal
    cost_per_1k_output: Decimal
    supports_streaming: bool = True
    supports_function_calling: bool = False
    default_latency_sla_ms: int = 5000
