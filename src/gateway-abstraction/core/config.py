"""
Configuration loading for gateway abstraction layer.
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class GatewayInstanceConfig:
    """Configuration for a single gateway instance."""

    type: str
    name: str
    base_url: str
    api_key: Optional[str] = None
    timeout: float = 60.0
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutingConfig:
    """Configuration for model routing."""

    strategy: str = "priority"  # priority, round_robin, least_latency
    model_routing: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class GatewayConfig:
    """Complete gateway configuration."""

    default_gateway: Optional[str] = None
    gateways: List[GatewayInstanceConfig] = field(default_factory=list)
    routing: RoutingConfig = field(default_factory=RoutingConfig)


def load_config(config_path: Optional[str] = None) -> GatewayConfig:
    """
    Load gateway configuration from YAML file.

    Args:
        config_path: Path to config file. If None, uses default location.

    Returns:
        Loaded configuration
    """
    if config_path is None:
        # Try common locations
        paths = [
            Path("config/gateway-abstraction/gateways.yaml"),
            Path("/etc/gateway-abstraction/gateways.yaml"),
            Path.home() / ".config/gateway-abstraction/gateways.yaml",
        ]
        for p in paths:
            if p.exists():
                config_path = str(p)
                break

    if config_path is None or not Path(config_path).exists():
        logger.warning("No gateway config file found, using defaults")
        return _default_config()

    try:
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)

        return _parse_config(data)

    except Exception as e:
        logger.error(f"Failed to load config from {config_path}: {e}")
        return _default_config()


def _parse_config(data: Dict[str, Any]) -> GatewayConfig:
    """Parse configuration dictionary."""
    gateways = []

    for gw_data in data.get("gateways", []):
        # Expand environment variables in api_key
        api_key = gw_data.get("api_key", "")
        if api_key and api_key.startswith("${") and api_key.endswith("}"):
            env_var = api_key[2:-1]
            api_key = os.environ.get(env_var, "")

        gateways.append(
            GatewayInstanceConfig(
                type=gw_data.get("type", ""),
                name=gw_data.get("name", ""),
                base_url=gw_data.get("base_url", ""),
                api_key=api_key,
                timeout=gw_data.get("timeout", 60.0),
                extra=gw_data.get("extra", {}),
            )
        )

    routing_data = data.get("routing", {})
    routing = RoutingConfig(
        strategy=routing_data.get("strategy", "priority"),
        model_routing=routing_data.get("model_routing", {}),
    )

    return GatewayConfig(
        default_gateway=data.get("default_gateway"),
        gateways=gateways,
        routing=routing,
    )


def _default_config() -> GatewayConfig:
    """Return default configuration."""
    return GatewayConfig(
        default_gateway="primary-litellm",
        gateways=[
            GatewayInstanceConfig(
                type="litellm",
                name="primary-litellm",
                base_url=os.environ.get("LITELLM_URL", "http://localhost:4000"),
                api_key=os.environ.get("LITELLM_MASTER_KEY", "$LITELLM_KEY"),
            ),
        ],
        routing=RoutingConfig(
            strategy="priority",
            model_routing={
                "*": ["primary-litellm"],
            },
        ),
    )
