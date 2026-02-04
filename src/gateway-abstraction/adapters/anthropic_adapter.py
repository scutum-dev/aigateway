"""
Direct Anthropic API adapter.

Provides direct access to Anthropic's Claude API without going through LiteLLM.
"""

import logging
import json
from typing import Optional, Set, List, Dict, Any, AsyncIterator
import httpx

from ..core.interface import AbstractGateway, GatewayCapability
from ..core.errors import GatewayConnectionError, GatewayAuthenticationError, GatewayRateLimitError
from ..models.request import ChatRequest
from ..models.response import ChatResponse

logger = logging.getLogger(__name__)


class AnthropicAdapter(AbstractGateway):
    """
    Direct Anthropic API adapter.

    Connects directly to Anthropic's Claude API.
    """

    ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1"
    ANTHROPIC_VERSION = "2024-01-01"

    def __init__(
        self,
        name: str,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 60.0,
        **kwargs,
    ):
        """
        Initialize Anthropic adapter.

        Args:
            name: Unique name for this adapter instance
            base_url: Anthropic API URL (defaults to api.anthropic.com)
            api_key: Anthropic API key
            timeout: Request timeout in seconds
        """
        self._name = name
        self._base_url = (base_url or self.ANTHROPIC_BASE_URL).rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._connected = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def gateway_type(self) -> str:
        return "anthropic"

    @property
    def capabilities(self) -> Set[GatewayCapability]:
        return {
            GatewayCapability.CHAT_COMPLETION,
            GatewayCapability.STREAMING,
            GatewayCapability.TOOL_USE,
            GatewayCapability.VISION,
        }

    @property
    def is_connected(self) -> bool:
        return self._connected and self._client is not None

    async def connect(self) -> None:
        """Initialize HTTP client for Anthropic."""
        if self._client is not None:
            return

        if not self._api_key:
            raise GatewayAuthenticationError(
                "API key required",
                gateway=self._name
            )

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self._api_key,
            "anthropic-version": self.ANTHROPIC_VERSION,
        }

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=self._timeout,
        )

        self._connected = True
        logger.info(f"Connected to Anthropic at {self._base_url}")

    async def disconnect(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
            self._connected = False
            logger.info("Disconnected from Anthropic")

    async def chat_completion(self, request: ChatRequest) -> ChatResponse:
        """Create a chat completion via Anthropic API."""
        if not self._client:
            await self.connect()

        try:
            response = await self._client.post(
                "/messages",
                json=request.to_anthropic_format(),
            )

            self._check_response_errors(response)

            data = response.json()
            return ChatResponse.from_anthropic(data, gateway=self._name)

        except httpx.RequestError as e:
            raise GatewayConnectionError(str(e), gateway=self._name)

    async def chat_completion_stream(
        self,
        request: ChatRequest
    ) -> AsyncIterator[ChatResponse]:
        """Create a streaming chat completion via Anthropic API."""
        if not self._client:
            await self.connect()

        request_data = request.to_anthropic_format()
        request_data["stream"] = True

        try:
            async with self._client.stream(
                "POST",
                "/messages",
                json=request_data,
            ) as response:
                self._check_response_errors(response)

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        try:
                            event = json.loads(data)
                            chunk = self._parse_stream_event(event, request.model)
                            if chunk:
                                yield chunk
                        except json.JSONDecodeError:
                            continue

        except httpx.RequestError as e:
            raise GatewayConnectionError(str(e), gateway=self._name)

    def _check_response_errors(self, response: httpx.Response) -> None:
        """Check response for errors and raise appropriate exceptions."""
        if response.status_code == 200:
            return

        if response.status_code == 401:
            raise GatewayAuthenticationError(
                "Invalid API key",
                gateway=self._name
            )

        if response.status_code == 429:
            retry_after = response.headers.get("retry-after")
            raise GatewayRateLimitError(
                "Rate limit exceeded",
                gateway=self._name,
                retry_after=float(retry_after) if retry_after else None
            )

        error_data = {}
        try:
            error_data = response.json()
        except Exception:
            pass

        raise GatewayConnectionError(
            f"Request failed: {response.status_code} - {error_data}",
            gateway=self._name
        )

    def _parse_stream_event(
        self,
        event: Dict[str, Any],
        model: str
    ) -> Optional[ChatResponse]:
        """Parse an Anthropic streaming event into ChatResponse."""
        event_type = event.get("type")

        if event_type == "content_block_delta":
            delta = event.get("delta", {})
            if delta.get("type") == "text_delta":
                return ChatResponse.stream_chunk(
                    content=delta.get("text"),
                    model=model,
                    gateway=self._name,
                )

        elif event_type == "message_stop":
            return ChatResponse.stream_chunk(
                content=None,
                model=model,
                finish_reason="stop",
                gateway=self._name,
            )

        return None

    async def list_models(self) -> List[Dict[str, Any]]:
        """
        List available Anthropic models.

        Note: Anthropic doesn't have a models endpoint, so we return
        a hardcoded list of known models.
        """
        return [
            {"id": "claude-3-opus-20240229", "object": "model"},
            {"id": "claude-3-sonnet-20240229", "object": "model"},
            {"id": "claude-3-haiku-20240307", "object": "model"},
            {"id": "claude-3-5-sonnet-20240620", "object": "model"},
            {"id": "claude-3-5-haiku-20241022", "object": "model"},
        ]

    async def health_check(self) -> Dict[str, Any]:
        """Check Anthropic API health."""
        # Anthropic doesn't have a health endpoint, so we just check connection
        return {
            "healthy": self._connected,
            "note": "No dedicated health endpoint",
        }
