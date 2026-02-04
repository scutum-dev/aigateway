"""
Custom gateway adapter template.

Provides a base for implementing custom gateway adapters
for proprietary or specialized AI backends.
"""

import logging
from typing import Optional, Set, List, Dict, Any, AsyncIterator, Callable
import httpx

from ..core.interface import AbstractGateway, GatewayCapability
from ..core.errors import GatewayConnectionError
from ..models.request import ChatRequest
from ..models.response import ChatResponse

logger = logging.getLogger(__name__)


class CustomAdapter(AbstractGateway):
    """
    Custom gateway adapter for specialized backends.

    This adapter can be configured with custom request/response
    transformers for non-standard APIs.
    """

    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: float = 60.0,
        capabilities: Optional[Set[str]] = None,
        request_transformer: Optional[Callable[[ChatRequest], Dict[str, Any]]] = None,
        response_transformer: Optional[Callable[[Dict[str, Any]], ChatResponse]] = None,
        chat_endpoint: str = "/v1/chat/completions",
        models_endpoint: str = "/v1/models",
        health_endpoint: str = "/health",
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ):
        """
        Initialize custom adapter.

        Args:
            name: Unique name for this adapter instance
            base_url: API base URL
            api_key: API key for authentication
            timeout: Request timeout in seconds
            capabilities: Set of capability strings
            request_transformer: Custom function to transform requests
            response_transformer: Custom function to transform responses
            chat_endpoint: Chat completion endpoint path
            models_endpoint: Models list endpoint path
            health_endpoint: Health check endpoint path
            headers: Additional headers to include
        """
        self._name = name
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

        # Parse capabilities
        self._capabilities = set()
        if capabilities:
            for cap in capabilities:
                try:
                    self._capabilities.add(GatewayCapability(cap))
                except ValueError:
                    logger.warning(f"Unknown capability: {cap}")
        else:
            self._capabilities = {
                GatewayCapability.CHAT_COMPLETION,
                GatewayCapability.STREAMING,
            }

        # Custom transformers
        self._request_transformer = request_transformer
        self._response_transformer = response_transformer

        # Endpoints
        self._chat_endpoint = chat_endpoint
        self._models_endpoint = models_endpoint
        self._health_endpoint = health_endpoint

        # Custom headers
        self._custom_headers = headers or {}

        self._client: Optional[httpx.AsyncClient] = None
        self._connected = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def gateway_type(self) -> str:
        return "custom"

    @property
    def capabilities(self) -> Set[GatewayCapability]:
        return self._capabilities

    @property
    def is_connected(self) -> bool:
        return self._connected and self._client is not None

    async def connect(self) -> None:
        """Initialize HTTP client."""
        if self._client is not None:
            return

        headers = {
            "Content-Type": "application/json",
            **self._custom_headers,
        }

        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=self._timeout,
        )

        self._connected = True
        logger.info(f"Connected to custom gateway at {self._base_url}")

    async def disconnect(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
            self._connected = False
            logger.info(f"Disconnected from custom gateway {self._name}")

    def _transform_request(self, request: ChatRequest) -> Dict[str, Any]:
        """Transform request using custom transformer or default."""
        if self._request_transformer:
            return self._request_transformer(request)
        return request.to_openai_format()

    def _transform_response(self, data: Dict[str, Any]) -> ChatResponse:
        """Transform response using custom transformer or default."""
        if self._response_transformer:
            return self._response_transformer(data)
        return ChatResponse.from_openai(data, gateway=self._name)

    async def chat_completion(self, request: ChatRequest) -> ChatResponse:
        """Create a chat completion."""
        if not self._client:
            await self.connect()

        try:
            request_data = self._transform_request(request)

            response = await self._client.post(
                self._chat_endpoint,
                json=request_data,
            )

            if response.status_code != 200:
                raise GatewayConnectionError(
                    f"Request failed: {response.status_code}",
                    gateway=self._name
                )

            data = response.json()
            return self._transform_response(data)

        except httpx.RequestError as e:
            raise GatewayConnectionError(str(e), gateway=self._name)

    async def chat_completion_stream(
        self,
        request: ChatRequest
    ) -> AsyncIterator[ChatResponse]:
        """Create a streaming chat completion."""
        if not self._client:
            await self.connect()

        try:
            request_data = self._transform_request(request)
            request_data["stream"] = True

            async with self._client.stream(
                "POST",
                self._chat_endpoint,
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
                            import json
                            chunk = json.loads(data)
                            yield ChatResponse.stream_chunk(
                                content=chunk.get("choices", [{}])[0].get("delta", {}).get("content"),
                                model=chunk.get("model", ""),
                                finish_reason=chunk.get("choices", [{}])[0].get("finish_reason"),
                                gateway=self._name,
                            )
                        except Exception:
                            continue

        except httpx.RequestError as e:
            raise GatewayConnectionError(str(e), gateway=self._name)

    async def list_models(self) -> List[Dict[str, Any]]:
        """List available models."""
        if not self._client:
            await self.connect()

        try:
            response = await self._client.get(self._models_endpoint)

            if response.status_code != 200:
                logger.warning(f"Failed to list models: {response.status_code}")
                return []

            data = response.json()
            return data.get("data", data.get("models", []))

        except httpx.RequestError as e:
            logger.error(f"Failed to list models: {e}")
            return []

    async def health_check(self) -> Dict[str, Any]:
        """Check gateway health."""
        if not self._client:
            return {"healthy": False, "error": "Not connected"}

        try:
            response = await self._client.get(self._health_endpoint)
            return {
                "healthy": response.status_code == 200,
                "status_code": response.status_code,
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}
