"""
Gateway Abstraction Layer

A pluggable interface for AI gateways allowing:
- Swap between LiteLLM, direct APIs, or custom backends
- Unified request/response models
- Automatic adapter discovery
- Configuration-based gateway selection
"""

from .core.interface import AbstractGateway, GatewayCapability
from .core.registry import GatewayRegistry
from .core.config import GatewayConfig, load_config
from .models.request import ChatRequest, Message, ToolCall
from .models.response import ChatResponse, Choice, Usage

__all__ = [
    "AbstractGateway",
    "GatewayCapability",
    "GatewayRegistry",
    "GatewayConfig",
    "load_config",
    "ChatRequest",
    "ChatResponse",
    "Message",
    "Choice",
    "Usage",
    "ToolCall",
]
