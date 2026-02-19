"""
Configuration for Workflow Engine service.
"""

import os
from dataclasses import dataclass


@dataclass
class Config:
    """Application configuration."""

    # Database
    database_url: str = os.getenv("DATABASE_URL", "postgresql://litellm:litellm@localhost:5432/litellm")

    # LiteLLM
    litellm_url: str = os.getenv("LITELLM_URL", "http://localhost:4000")
    litellm_api_key: str = os.getenv("LITELLM_API_KEY", "")

    # Agent Gateway (for MCP)
    agent_gateway_url: str = os.getenv("AGENT_GATEWAY_URL", "http://localhost:3000")

    # OpenTelemetry
    otel_endpoint: str = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

    # Workflow settings
    default_timeout_seconds: int = int(os.getenv("DEFAULT_TIMEOUT_SECONDS", "300"))
    max_workflow_steps: int = int(os.getenv("MAX_WORKFLOW_STEPS", "50"))

    # Server
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8085"))


config = Config()
