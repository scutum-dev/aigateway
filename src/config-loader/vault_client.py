"""
Vault client for secrets management.
"""

import os
import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)


class VaultClient:
    """
    HashiCorp Vault client for secrets retrieval.

    Supports both KV v1 and KV v2 secrets engines.
    """

    def __init__(
        self,
        addr: Optional[str] = None,
        token: Optional[str] = None,
        namespace: Optional[str] = None,
        kv_version: int = 2,
        timeout: float = 10.0,
    ):
        """
        Initialize Vault client.

        Args:
            addr: Vault server address. Defaults to VAULT_ADDR env var.
            token: Vault token. Defaults to VAULT_TOKEN env var.
            namespace: Vault namespace (Enterprise feature).
            kv_version: KV secrets engine version (1 or 2).
            timeout: Request timeout in seconds.
        """
        self.addr = addr or os.getenv("VAULT_ADDR", "http://localhost:8200")
        self.token = token or os.getenv("VAULT_TOKEN")
        self.namespace = namespace or os.getenv("VAULT_NAMESPACE")
        self.kv_version = kv_version
        self.timeout = timeout

        # Remove trailing slash from address
        self.addr = self.addr.rstrip("/")

        # HTTP client
        self._client: Optional[httpx.Client] = None

    @property
    def client(self) -> httpx.Client:
        """Get HTTP client with Vault headers."""
        if self._client is None:
            headers = {}
            if self.token:
                headers["X-Vault-Token"] = self.token
            if self.namespace:
                headers["X-Vault-Namespace"] = self.namespace

            self._client = httpx.Client(
                base_url=self.addr,
                headers=headers,
                timeout=self.timeout,
            )
        return self._client

    def _build_path(self, path: str) -> str:
        """Build the API path for KV operations."""
        # Handle KV v2 path structure (secret/data/path)
        if self.kv_version == 2:
            parts = path.split("/", 1)
            if len(parts) == 2:
                mount, subpath = parts
                return f"/v1/{mount}/data/{subpath}"
            return f"/v1/{path}/data"

        # KV v1 path (secret/path)
        return f"/v1/{path}"

    def get_secret(self, path: str, key: str) -> Optional[str]:
        """
        Get a specific secret value from Vault.

        Args:
            path: Path to the secret (e.g., "secret/ai-gateway/dev/providers/openai").
            key: Key within the secret (e.g., "api_key").

        Returns:
            Secret value or None if not found.
        """
        try:
            response = self.client.get(self._build_path(path))

            if response.status_code == 404:
                logger.debug(f"Secret not found: {path}")
                return None

            response.raise_for_status()
            data = response.json()

            # Extract data based on KV version
            if self.kv_version == 2:
                secrets = data.get("data", {}).get("data", {})
            else:
                secrets = data.get("data", {})

            return secrets.get(key)

        except httpx.HTTPError as e:
            logger.error(f"Failed to get secret from {path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting secret: {e}")
            return None

    def get_secrets(self, path: str) -> dict[str, str]:
        """
        Get all secrets at a given path.

        Args:
            path: Path to the secrets.

        Returns:
            Dictionary of all secrets at the path.
        """
        try:
            response = self.client.get(self._build_path(path))

            if response.status_code == 404:
                logger.debug(f"Secrets not found: {path}")
                return {}

            response.raise_for_status()
            data = response.json()

            # Extract data based on KV version
            if self.kv_version == 2:
                return data.get("data", {}).get("data", {})
            return data.get("data", {})

        except Exception as e:
            logger.error(f"Failed to get secrets from {path}: {e}")
            return {}

    def list_secrets(self, path: str) -> list[str]:
        """
        List secret keys at a given path.

        Args:
            path: Path to list.

        Returns:
            List of secret keys.
        """
        try:
            # For KV v2, use metadata path
            if self.kv_version == 2:
                parts = path.split("/", 1)
                if len(parts) == 2:
                    mount, subpath = parts
                    list_path = f"/v1/{mount}/metadata/{subpath}"
                else:
                    list_path = f"/v1/{path}/metadata"
            else:
                list_path = f"/v1/{path}"

            response = self.client.request("LIST", list_path)

            if response.status_code == 404:
                return []

            response.raise_for_status()
            data = response.json()

            return data.get("data", {}).get("keys", [])

        except Exception as e:
            logger.error(f"Failed to list secrets at {path}: {e}")
            return []

    def put_secret(self, path: str, data: dict[str, str]) -> bool:
        """
        Write secrets to Vault.

        Args:
            path: Path to write to.
            data: Dictionary of secrets.

        Returns:
            True if successful, False otherwise.
        """
        try:
            # For KV v2, wrap in data envelope
            if self.kv_version == 2:
                payload = {"data": data}
            else:
                payload = data

            response = self.client.post(
                self._build_path(path),
                json=payload,
            )
            response.raise_for_status()
            return True

        except Exception as e:
            logger.error(f"Failed to write secret to {path}: {e}")
            return False

    def health_check(self) -> bool:
        """
        Check Vault health status.

        Returns:
            True if Vault is healthy, False otherwise.
        """
        try:
            response = self.client.get("/v1/sys/health")
            return response.status_code in (200, 429, 472, 473)
        except Exception:
            return False

    def close(self):
        """Close the HTTP client."""
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
