"""
Gateway registry for managing and discovering gateway adapters.
"""

import logging
from typing import Dict, List, Optional, Type, Any
from .interface import AbstractGateway, GatewayCapability
from .errors import GatewayNotFoundError

logger = logging.getLogger(__name__)


class GatewayRegistry:
    """
    Registry for gateway adapters.

    Manages gateway instances and provides lookup functionality
    for routing and gateway selection.
    """

    def __init__(self):
        """Initialize the registry."""
        self._adapters: Dict[str, Type[AbstractGateway]] = {}
        self._instances: Dict[str, AbstractGateway] = {}
        self._default_gateway: Optional[str] = None

    def register_adapter(
        self,
        gateway_type: str,
        adapter_class: Type[AbstractGateway]
    ) -> None:
        """
        Register a gateway adapter class.

        Args:
            gateway_type: Type identifier (e.g., "litellm", "openai")
            adapter_class: Adapter class to register
        """
        self._adapters[gateway_type] = adapter_class
        logger.info(f"Registered gateway adapter: {gateway_type}")

    def create_gateway(
        self,
        gateway_type: str,
        name: str,
        config: Dict[str, Any]
    ) -> AbstractGateway:
        """
        Create a gateway instance from registered adapter.

        Args:
            gateway_type: Type of gateway to create
            name: Unique name for this instance
            config: Configuration for the gateway

        Returns:
            Configured gateway instance
        """
        if gateway_type not in self._adapters:
            raise GatewayNotFoundError(f"Unknown gateway type: {gateway_type}")

        adapter_class = self._adapters[gateway_type]
        instance = adapter_class(name=name, **config)
        self._instances[name] = instance

        logger.info(f"Created gateway instance: {name} (type: {gateway_type})")
        return instance

    def get_gateway(self, name: str) -> AbstractGateway:
        """
        Get a gateway instance by name.

        Args:
            name: Gateway name

        Returns:
            Gateway instance

        Raises:
            GatewayNotFoundError: If gateway not found
        """
        if name not in self._instances:
            raise GatewayNotFoundError(f"Gateway not found: {name}")
        return self._instances[name]

    def get_default_gateway(self) -> Optional[AbstractGateway]:
        """
        Get the default gateway.

        Returns:
            Default gateway or None
        """
        if self._default_gateway:
            return self._instances.get(self._default_gateway)
        return None

    def set_default_gateway(self, name: str) -> None:
        """
        Set the default gateway.

        Args:
            name: Gateway name to set as default
        """
        if name not in self._instances:
            raise GatewayNotFoundError(f"Gateway not found: {name}")
        self._default_gateway = name
        logger.info(f"Set default gateway: {name}")

    def list_gateways(self) -> List[Dict[str, Any]]:
        """
        List all registered gateway instances.

        Returns:
            List of gateway info dicts
        """
        return [
            {
                "name": gw.name,
                "type": gw.gateway_type,
                "capabilities": [c.value for c in gw.capabilities],
                "is_connected": gw.is_connected,
                "is_default": gw.name == self._default_gateway,
            }
            for gw in self._instances.values()
        ]

    def find_gateway_for_model(
        self,
        model: str,
        model_routing: Optional[Dict[str, List[str]]] = None
    ) -> Optional[AbstractGateway]:
        """
        Find a gateway that can handle a specific model.

        Args:
            model: Model name or pattern
            model_routing: Optional routing rules mapping model patterns to gateway names

        Returns:
            Suitable gateway or None
        """
        if model_routing:
            # Check exact match first
            if model in model_routing:
                gateway_names = model_routing[model]
                for name in gateway_names:
                    if name in self._instances and self._instances[name].is_connected:
                        return self._instances[name]

            # Check pattern matches
            import fnmatch
            for pattern, gateway_names in model_routing.items():
                if fnmatch.fnmatch(model, pattern):
                    for name in gateway_names:
                        if name in self._instances and self._instances[name].is_connected:
                            return self._instances[name]

        # Fall back to default
        return self.get_default_gateway()

    def find_gateways_with_capability(
        self,
        capability: GatewayCapability
    ) -> List[AbstractGateway]:
        """
        Find all gateways that support a capability.

        Args:
            capability: Required capability

        Returns:
            List of gateways with that capability
        """
        return [
            gw for gw in self._instances.values()
            if gw.supports(capability) and gw.is_connected
        ]

    async def connect_all(self) -> None:
        """Connect all registered gateways."""
        for gw in self._instances.values():
            try:
                await gw.connect()
            except Exception as e:
                logger.error(f"Failed to connect gateway {gw.name}: {e}")

    async def disconnect_all(self) -> None:
        """Disconnect all registered gateways."""
        for gw in self._instances.values():
            try:
                await gw.disconnect()
            except Exception as e:
                logger.error(f"Failed to disconnect gateway {gw.name}: {e}")

    async def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Perform health checks on all gateways.

        Returns:
            Dict mapping gateway name to health status
        """
        results = {}
        for name, gw in self._instances.items():
            try:
                results[name] = await gw.health_check()
            except Exception as e:
                results[name] = {"healthy": False, "error": str(e)}
        return results


# Global registry instance
_registry: Optional[GatewayRegistry] = None


def get_registry() -> GatewayRegistry:
    """Get the global gateway registry."""
    global _registry
    if _registry is None:
        _registry = GatewayRegistry()
    return _registry
