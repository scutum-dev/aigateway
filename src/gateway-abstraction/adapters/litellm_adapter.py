"""
LiteLLM gateway adapter.

Primary adapter for the AI Gateway platform, providing access
to all models through LiteLLM's unified proxy.
"""

import logging
import json
from typing import Optional, Set, List, Dict, Any, AsyncIterator
import httpx

from ..core.interface import AbstractGateway, GatewayCapability
from ..core.errors import GatewayConnectionError, GatewayAuthenticationError
from ..models.request import ChatRequest
from ..models.response import ChatResponse

logger = logging.getLogger(__name__)


class LiteLLMAdapter(AbstractGateway):
    """
    LiteLLM gateway adapter.

    Provides access to all models configured in LiteLLM proxy.
    This is the primary adapter for the AI Gateway platform.
    """

    def __init__(
        self,
        name: str,
        base_url: str = "http://localhost:4000",
        api_key: Optional[str] = None,
        timeout: float = 60.0,
        **kwargs,
    ):
        """
        Initialize LiteLLM adapter.

        Args:
            name: Unique name for this adapter instance
            base_url: LiteLLM proxy URL
            api_key: API key for authentication
            timeout: Request timeout in seconds
        """
        self._name = name
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._connected = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def gateway_type(self) -> str:
        return "litellm"

    @property
    def capabilities(self) -> Set[GatewayCapability]:
        return {
            GatewayCapability.CHAT_COMPLETION,
            GatewayCapability.STREAMING,
            GatewayCapability.FUNCTION_CALLING,
            GatewayCapability.TOOL_USE,
            GatewayCapability.VISION,
            GatewayCapability.JSON_MODE,
            GatewayCapability.EMBEDDINGS,
        }

    @property
    def is_connected(self) -> bool:
        return self._connected and self._client is not None

    async def connect(self) -> None:
        """Establish connection to LiteLLM proxy."""
        if self._client is not None:
            return

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=self._timeout,
        )

        # Test connection
        try:
            response = await self._client.get("/health/liveliness")
            if response.status_code != 200:
                raise GatewayConnectionError(
                    f"Health check failed: {response.status_code}",
                    gateway=self._name
                )
            self._connected = True
            logger.info(f"Connected to LiteLLM at {self._base_url}")
        except httpx.RequestError as e:
            raise GatewayConnectionError(
                f"Failed to connect: {e}",
                gateway=self._name
            )

    async def disconnect(self) -> None:
        """Close connection to LiteLLM proxy."""
        if self._client:
            await self._client.aclose()
            self._client = None
            self._connected = False
            logger.info(f"Disconnected from LiteLLM")

    async def chat_completion(self, request: ChatRequest) -> ChatResponse:
        """Create a chat completion through LiteLLM."""
        if not self._client:
            await self.connect()

        try:
            response = await self._client.post(
                "/v1/chat/completions",
                json=request.to_openai_format(),
            )

            if response.status_code == 401:
                raise GatewayAuthenticationError(
                    "Authentication failed",
                    gateway=self._name
                )

            if response.status_code != 200:
                error_data = response.json() if response.content else {}
                raise GatewayConnectionError(
                    f"Request failed: {response.status_code} - {error_data}",
                    gateway=self._name
                )

            data = response.json()
            return ChatResponse.from_openai(data, gateway=self._name)

        except httpx.RequestError as e:
            raise GatewayConnectionError(str(e), gateway=self._name)

    async def chat_completion_stream(
        self,
        request: ChatRequest
    ) -> AsyncIterator[ChatResponse]:
        """Create a streaming chat completion through LiteLLM."""
        if not self._client:
            await self.connect()

        # Ensure streaming is enabled
        request_data = request.to_openai_format()
        request_data["stream"] = True

        try:
            async with self._client.stream(
                "POST",
                "/v1/chat/completions",
                json=request_data,
            ) as response:
                if response.status_code != 200:
                    raise GatewayConnectionError(
                        f"Stream request failed: {response.status_code}",
                        gateway=self._name
                    )

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            yield self._parse_stream_chunk(chunk)
                        except json.JSONDecodeError:
                            continue

        except httpx.RequestError as e:
            raise GatewayConnectionError(str(e), gateway=self._name)

    def _parse_stream_chunk(self, chunk: Dict[str, Any]) -> ChatResponse:
        """Parse a streaming chunk into ChatResponse."""
        return ChatResponse.stream_chunk(
            content=chunk.get("choices", [{}])[0].get("delta", {}).get("content"),
            model=chunk.get("model", ""),
            finish_reason=chunk.get("choices", [{}])[0].get("finish_reason"),
            gateway=self._name,
        )

    async def list_models(self) -> List[Dict[str, Any]]:
        """List available models from LiteLLM."""
        if not self._client:
            await self.connect()

        try:
            response = await self._client.get("/v1/models")

            if response.status_code != 200:
                logger.warning(f"Failed to list models: {response.status_code}")
                return []

            data = response.json()
            return data.get("data", [])

        except httpx.RequestError as e:
            logger.error(f"Failed to list models: {e}")
            return []

    async def health_check(self) -> Dict[str, Any]:
        """Check LiteLLM health."""
        if not self._client:
            return {"healthy": False, "error": "Not connected"}

        try:
            response = await self._client.get("/health/liveliness")
            return {
                "healthy": response.status_code == 200,
                "status_code": response.status_code,
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}
