"""
Pydantic models for Admin API.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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


class MCPServerUpdate(BaseModel):
    """Update MCP server configuration."""

    name: Optional[str] = None
    server_type: Optional[str] = None
    command: Optional[str] = None
    url: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    is_active: Optional[bool] = None


# A2A Agents
class A2AAgentConfig(BaseModel):
    """A2A agent configuration."""

    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    url: str
    skills: List[str] = Field(default_factory=list)
    is_active: bool = True


class A2AAgentCreate(BaseModel):
    """Create A2A agent configuration."""

    name: str
    description: Optional[str] = None
    url: str
    skills: List[str] = Field(default_factory=list)


class A2AAgentUpdate(BaseModel):
    """Update A2A agent configuration."""

    name: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    skills: Optional[List[str]] = None
    is_active: Optional[bool] = None


# Workflows
class WorkflowSummary(BaseModel):
    """Workflow summary for listing."""

    id: str
    name: str
    template_type: Optional[str]
    description: Optional[str]
    is_active: bool
    created_at: Optional[datetime]


class WorkflowExecuteRequest(BaseModel):
    """Request to execute a workflow."""

    workflow_name: Optional[str] = None
    template_type: str
    input_text: str
    user_id: Optional[str] = None
    team_id: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class WorkflowExecutionSummary(BaseModel):
    """Workflow execution summary."""

    id: str
    workflow_name: Optional[str] = None
    status: str
    total_cost: Optional[float] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class WorkflowCreate(BaseModel):
    """Create a new workflow definition."""

    name: str
    template_type: str
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


# Settings
class PlatformSettings(BaseModel):
    """Platform settings."""

    default_model: str = "gpt-4o-mini"
    global_rate_limit: int = 1000
    enable_caching: bool = True
    cache_ttl_seconds: int = 3600
    enable_cost_tracking: bool = True
    enable_budget_enforcement: bool = True
    enable_guardrails: bool = True
    maintenance_mode: bool = False
