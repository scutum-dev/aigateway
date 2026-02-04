"""
Abstract Gateway interface definition.

Defines the contract that all gateway adapters must implement.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, AsyncIterator, Optional, Set
from enum import Enum

from ..models.request import ChatRequest
from ..models.response import ChatResponse


class GatewayCapability(str, Enum):
    """Capabilities that a gateway may support."""
    CHAT_COMPLETION = "chat_completion"
    STREAMING = "streaming"
    FUNCTION_CALLING = "function_calling"
    TOOL_USE = "tool_use"
    VISION = "vision"
    JSON_MODE = "json_mode"
    EMBEDDINGS = "embeddings"
    IMAGES = "images"
    AUDIO = "audio"


class AbstractGateway(ABC):
    """
    Abstract base class for AI gateway implementations.

    All gateway adapters must implement this interface to be
    compatible with the gateway abstraction layer.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique name of this gateway instance.

        Returns:
            Gateway name (e.g., "primary-litellm", "direct-openai")
        """
        pass

    @property
    @abstractmethod
    def gateway_type(self) -> str:
        """
        Type of gateway (e.g., "litellm", "openai", "anthropic").

        Returns:
            Gateway type identifier
        """
        pass

    @property
    @abstractmethod
    def capabilities(self) -> Set[GatewayCapability]:
        """
        Set of capabilities this gateway supports.

        Returns:
            Set of GatewayCapability values
        """
        pass

    @property
    def is_connected(self) -> bool:
        """
        Check if gateway is currently connected and healthy.

        Returns:
            True if connected
        """
        return True

    @abstractmethod
    async def connect(self) -> None:
        """
        Establish connection to the gateway.

        Called when the gateway is first used or needs reconnection.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Close connection to the gateway.

        Called during cleanup.
        """
        pass

    @abstractmethod
    async def chat_completion(self, request: ChatRequest) -> ChatResponse:
        """
        Create a chat completion.

        Args:
            request: Chat completion request

        Returns:
            Chat completion response
        """
        pass

    @abstractmethod
    async def chat_completion_stream(
        self,
        request: ChatRequest
    ) -> AsyncIterator[ChatResponse]:
        """
        Create a streaming chat completion.

        Args:
            request: Chat completion request

        Yields:
            Streaming response chunks
        """
        pass

    @abstractmethod
    async def list_models(self) -> List[Dict[str, Any]]:
        """
        List available models from this gateway.

        Returns:
            List of model information dicts
        """
        pass

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the gateway.

        Returns:
            Health status dict with at least {"healthy": bool}
        """
        return {"healthy": self.is_connected}

    def supports(self, capability: GatewayCapability) -> bool:
        """
        Check if gateway supports a capability.

        Args:
            capability: Capability to check

        Returns:
            True if supported
        """
        return capability in self.capabilities

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r}, type={self.gateway_type!r})"
