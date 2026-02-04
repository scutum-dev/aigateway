"""
Core gateway abstraction components.
"""

from .interface import AbstractGateway, GatewayCapability
from .registry import GatewayRegistry
from .config import GatewayConfig, load_config
from .errors import (
    GatewayError,
    GatewayNotFoundError,
    GatewayConnectionError,
    GatewayAuthenticationError,
    GatewayRateLimitError,
)

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
