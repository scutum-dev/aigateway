"""
Core gateway abstraction components.
"""

from .config import GatewayConfig, load_config
from .errors import (
    GatewayAuthenticationError,
    GatewayConnectionError,
    GatewayError,
    GatewayNotFoundError,
    GatewayRateLimitError,
)
from .interface import AbstractGateway, GatewayCapability
from .registry import GatewayRegistry

__all__ = [
    "AbstractGateway",
    "GatewayCapability",
    "GatewayRegistry",
    "GatewayConfig",
    "load_config",
    "GatewayError",
    "GatewayNotFoundError",
    "GatewayConnectionError",
    "GatewayAuthenticationError",
    "GatewayRateLimitError",
]
