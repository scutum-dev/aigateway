"""
Configuration Loader with environment detection and Vault integration.
"""

import os
import yaml
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from functools import lru_cache

from .vault_client import VaultClient


class Environment(Enum):
    """Supported deployment environments."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

    @classmethod
    def from_string(cls, value: str) -> "Environment":
        """Convert string to Environment enum."""
        mapping = {
            "dev": cls.DEVELOPMENT,
            "development": cls.DEVELOPMENT,
            "staging": cls.STAGING,
            "stg": cls.STAGING,
            "prod": cls.PRODUCTION,
            "production": cls.PRODUCTION,
        }
        return mapping.get(value.lower(), cls.DEVELOPMENT)


class ConfigLoader:
    """
    Environment-aware configuration loader with Vault integration.

    Loads configuration from YAML files and secrets from Vault,
    merging base config with environment-specific overrides.
    """

    def __init__(
        self,
        environment: Optional[Environment] = None,
        config_dir: Optional[str] = None,
        vault_client: Optional[VaultClient] = None,
    ):
        """
        Initialize the configuration loader.

        Args:
            environment: Target environment. Auto-detected if not specified.
            config_dir: Directory containing feature flag YAML files.
            vault_client: Vault client for secrets. Created if not provided.
        """
        self.environment = environment or self._detect_environment()
        self.config_dir = Path(config_dir or self._default_config_dir())
        self._vault_client = vault_client

        # Load and merge configurations
        self._base_config = self._load_yaml("base.yaml")
        self._env_config = self._load_yaml(f"{self._env_filename()}.yaml")
        self._merged_config = self._deep_merge(self._base_config, self._env_config)

        # Cache for secrets
        self._secrets_cache: dict[str, Any] = {}

    @property
    def vault_client(self) -> VaultClient:
        """Lazy-load Vault client."""
        if self._vault_client is None:
            self._vault_client = VaultClient(
                addr=os.getenv("VAULT_ADDR", "http://localhost:8200"),
                token=os.getenv("VAULT_TOKEN"),
            )
        return self._vault_client

    @property
    def vault_prefix(self) -> str:
        """Get the Vault path prefix for current environment."""
        return self._merged_config.get("vault_prefix", f"secret/ai-gateway/{self.environment.value}")

    def _detect_environment(self) -> Environment:
        """Detect environment from environment variables."""
        env_var = os.getenv("ENVIRONMENT") or os.getenv("ENV") or os.getenv("DEPLOY_ENV")
        if env_var:
            return Environment.from_string(env_var)

        # Check for Kubernetes namespace hints
        namespace = os.getenv("KUBERNETES_NAMESPACE") or os.getenv("K8S_NAMESPACE")
        if namespace:
            if "prod" in namespace.lower():
                return Environment.PRODUCTION
            elif "staging" in namespace.lower() or "stg" in namespace.lower():
                return Environment.STAGING

        return Environment.DEVELOPMENT

    def _default_config_dir(self) -> str:
        """Get default configuration directory."""
        # Check common locations
        candidates = [
            "/etc/ai-gateway/feature-flags",
            "/app/config/feature-flags",
            Path(__file__).parent.parent.parent / "config" / "feature-flags",
        ]
        for candidate in candidates:
            if Path(candidate).exists():
                return str(candidate)
        return str(candidates[-1])

    def _env_filename(self) -> str:
        """Get environment-specific config filename."""
        mapping = {
            Environment.DEVELOPMENT: "dev",
            Environment.STAGING: "staging",
            Environment.PRODUCTION: "production",
        }
        return mapping[self.environment]

    def _load_yaml(self, filename: str) -> dict:
        """Load YAML configuration file."""
        filepath = self.config_dir / filename
        if not filepath.exists():
            return {}

        with open(filepath) as f:
            return yaml.safe_load(f) or {}

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """Deep merge two dictionaries, with override taking precedence."""
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    # Feature Flag Methods

    def feature_enabled(self, feature_name: str) -> bool:
        """
        Check if a feature is enabled for the current environment.

        Args:
            feature_name: Name of the feature flag.

        Returns:
            True if the feature is enabled, False otherwise.
        """
        features = self._merged_config.get("features", {})
        return features.get(feature_name, False)

    def get_features(self) -> dict[str, bool]:
        """Get all feature flags for the current environment."""
        return self._merged_config.get("features", {}).copy()

    # Service Configuration Methods

    def get_service_config(self, service: str, key: Optional[str] = None) -> Any:
        """
        Get configuration for a specific service.

        Args:
            service: Service name (e.g., "litellm", "policy_router").
            key: Optional specific config key. Returns all config if not specified.

        Returns:
            Service configuration value or dict.
        """
        services = self._merged_config.get("services", {})
        service_config = services.get(service, {})

        if key is None:
            return service_config.copy()
        return service_config.get(key)

    def get_infrastructure_config(self, component: str, key: Optional[str] = None) -> Any:
        """
        Get infrastructure configuration.

        Args:
            component: Component name (e.g., "postgres", "redis").
            key: Optional specific config key.

        Returns:
            Infrastructure configuration value or dict.
        """
        infra = self._merged_config.get("infrastructure", {})
        component_config = infra.get(component, {})

        if key is None:
            return component_config.copy()
        return component_config.get(key)

    def get_endpoint(self, service: str) -> Optional[str]:
        """Get the endpoint URL for a service."""
        endpoints = self._merged_config.get("endpoints", {})
        return endpoints.get(service)

    def get_tls_config(self) -> dict:
        """Get TLS configuration for current environment."""
        return self._merged_config.get("tls", {}).copy()

    def get_resources(self, service: str) -> dict:
        """Get Kubernetes resource limits for a service."""
        resources = self._merged_config.get("resources", {})
        return resources.get(service, {}).copy()

    # Vault Secrets Methods

    def get_secret(self, path: str, key: str, use_cache: bool = True) -> Optional[str]:
        """
        Get a secret from Vault.

        Args:
            path: Relative path within environment prefix (e.g., "providers/openai").
            key: Secret key to retrieve (e.g., "api_key").
            use_cache: Whether to use cached value if available.

        Returns:
            Secret value or None if not found.
        """
        full_path = f"{self.vault_prefix}/{path}"
        cache_key = f"{full_path}:{key}"

        if use_cache and cache_key in self._secrets_cache:
            return self._secrets_cache[cache_key]

        try:
            secret = self.vault_client.get_secret(full_path, key)
            if secret:
                self._secrets_cache[cache_key] = secret
            return secret
        except Exception:
            return None

    def get_all_secrets(self, path: str) -> dict[str, str]:
        """
        Get all secrets at a given path.

        Args:
            path: Relative path within environment prefix.

        Returns:
            Dictionary of all secrets at the path.
        """
        full_path = f"{self.vault_prefix}/{path}"
        return self.vault_client.get_secrets(full_path)

    def clear_secrets_cache(self):
        """Clear the secrets cache."""
        self._secrets_cache.clear()

    # Environment Info

    def get_environment_info(self) -> dict:
        """Get information about the current environment configuration."""
        return {
            "environment": self.environment.value,
            "vault_prefix": self.vault_prefix,
            "config_dir": str(self.config_dir),
            "features_enabled": sum(1 for v in self.get_features().values() if v),
            "features_total": len(self.get_features()),
            "tls_enabled": self.get_tls_config().get("enabled", False),
        }

    def to_env_vars(self) -> dict[str, str]:
        """
        Export configuration as environment variables.
        Useful for passing config to subprocesses.

        Returns:
            Dictionary of environment variable names and values.
        """
        env_vars = {
            "ENVIRONMENT": self.environment.value,
            "VAULT_PREFIX": self.vault_prefix,
        }

        # Add feature flags
        for feature, enabled in self.get_features().items():
            env_name = f"FEATURE_{feature.upper()}"
            env_vars[env_name] = "true" if enabled else "false"

        # Add service endpoints
        for service, url in self._merged_config.get("endpoints", {}).items():
            env_name = f"{service.upper()}_URL"
            env_vars[env_name] = url

        return env_vars


# Singleton instance
_config_instance: Optional[ConfigLoader] = None


@lru_cache(maxsize=1)
def get_config(
    environment: Optional[str] = None,
    config_dir: Optional[str] = None,
) -> ConfigLoader:
    """
    Get the singleton configuration loader.

    Args:
        environment: Optional environment override.
        config_dir: Optional config directory override.

    Returns:
        ConfigLoader singleton instance.
    """
    env = Environment.from_string(environment) if environment else None
    return ConfigLoader(environment=env, config_dir=config_dir)
