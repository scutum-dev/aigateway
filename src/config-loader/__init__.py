"""
AI Gateway Configuration Loader

Environment-aware configuration management with Vault integration.
Loads feature flags and secrets based on the target environment.

Usage:
    from config_loader import ConfigLoader, get_config

    # Get singleton config for current environment
    config = get_config()

    # Access feature flags
    if config.feature_enabled("debug_mode"):
        enable_debug()

    # Access secrets from Vault
    openai_key = config.get_secret("providers/openai", "api_key")

    # Access service configuration
    replicas = config.get_service_config("litellm", "replicas")
"""

from .loader import ConfigLoader, get_config, Environment
from .vault_client import VaultClient

__all__ = ["ConfigLoader", "get_config", "Environment", "VaultClient"]
__version__ = "1.0.0"
