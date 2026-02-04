"""
Pydantic models for Admin API.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


# Model Configuration
class ModelConfig(BaseModel):
    """Model configuration for routing."""
    model_id: str
    provider: str
    tier: str = "standard"
    cost_per_1k_input: float
    cost_per_1k_output: float
    supports_streaming: bool = True
    supports_function_calling: bool = False
    supports_vision: bool = False
    default_latency_sla_ms: int = 5000
    is_active: bool = True


class ModelConfigUpdate(BaseModel):
    """Update model configuration."""
    tier: Optional[str] = None
    cost_per_1k_input: Optional[float] = None
    cost_per_1k_output: Optional[float] = None
    supports_streaming: Optional[bool] = None
    supports_function_calling: Optional[bool] = None
    supports_vision: Optional[bool] = None
    default_latency_sla_ms: Optional[int] = None
    is_active: Optional[bool] = None


# Routing Policies
class RoutingPolicy(BaseModel):
    """Routing policy definition."""
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    priority: int = 0
    condition: str  # Cedar-style condition
    action: str  # permit or forbid
    target_models: Optional[List[str]] = None
    is_active: bool = True


class RoutingPolicyCreate(BaseModel):
    """Create routing policy."""
    name: str
    description: Optional[str] = None
    priority: int = 0
    condition: str
    action: str = "permit"
    target_models: Optional[List[str]] = None


# Budgets
class Budget(BaseModel):
    """Budget configuration."""
    id: Optional[str] = None
    name: str
    entity_type: str  # user, team, global
    entity_id: Optional[str] = None
    monthly_limit: float
    current_spend: float = 0.0
    soft_limit_percent: float = 0.8
    hard_limit_percent: float = 1.0
    alert_email: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BudgetCreate(BaseModel):
    """Create budget."""
    name: str
    entity_type: str
    entity_id: Optional[str] = None
    monthly_limit: float
    soft_limit_percent: float = 0.8
    hard_limit_percent: float = 1.0
    alert_email: Optional[str] = None


class BudgetUpdate(BaseModel):
    """Update budget."""
    name: Optional[str] = None
    monthly_limit: Optional[float] = None
    soft_limit_percent: Optional[float] = None
    hard_limit_percent: Optional[float] = None
    alert_email: Optional[str] = None
    is_active: Optional[bool] = None


# Teams
class Team(BaseModel):
    """Team configuration."""
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    monthly_budget: Optional[float] = None
    members: List[str] = Field(default_factory=list)
    default_model: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None


class TeamCreate(BaseModel):
    """Create team."""
    name: str
    description: Optional[str] = None
    monthly_budget: Optional[float] = None
    default_model: Optional[str] = None


class TeamUpdate(BaseModel):
    """Update team."""
    name: Optional[str] = None
    description: Optional[str] = None
    monthly_budget: Optional[float] = None
    default_model: Optional[str] = None
    is_active: Optional[bool] = None


class TeamMember(BaseModel):
    """Team member."""
    user_id: str
    role: str = "member"  # member, admin


# MCP Servers
class MCPServerConfig(BaseModel):
    """MCP server configuration."""
    id: Optional[str] = None
    name: str
    server_type: str  # stdio, http
    command: Optional[str] = None  # For stdio servers
    url: Optional[str] = None  # For HTTP servers
    args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    tools: List[str] = Field(default_factory=list)
    is_active: bool = True


class MCPServerCreate(BaseModel):
    """Create MCP server configuration."""
    name: str
    server_type: str
    command: Optional[str] = None
    url: Optional[str] = None
    args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)


# Workflows
class WorkflowSummary(BaseModel):
    """Workflow summary for listing."""
    id: str
    name: str
    template_type: Optional[str]
    description: Optional[str]
    is_active: bool
    created_at: Optional[datetime]


# Metrics
class RealtimeMetrics(BaseModel):
    """Real-time platform metrics."""
    timestamp: datetime
    requests_per_minute: int
    active_users: int
    total_cost_today: float
    total_tokens_today: int
    average_latency_ms: float
    error_rate: float
    model_usage: Dict[str, int]
    provider_status: Dict[str, bool]


# Settings
class PlatformSettings(BaseModel):
    """Platform settings."""
    default_model: str = "gpt-4o-mini"
    global_rate_limit: int = 1000
    enable_caching: bool = True
    cache_ttl_seconds: int = 3600
    enable_cost_tracking: bool = True
    enable_budget_enforcement: bool = True
    enable_routing_policies: bool = True
    maintenance_mode: bool = False
