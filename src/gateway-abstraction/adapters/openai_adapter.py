"""
Direct OpenAI API adapter.

Provides direct access to OpenAI's API without going through LiteLLM.
Useful for fallback or when specific OpenAI features are needed.
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


class OpenAIAdapter(AbstractGateway):
    """
    Direct OpenAI API adapter.

    Connects directly to OpenAI's API for chat completions.
    """

    OPENAI_BASE_URL = "https://api.openai.com/v1"

    def __init__(
        self,
        name: str,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        organization: Optional[str] = None,
        timeout: float = 60.0,
        **kwargs,
    ):
        """
        Initialize OpenAI adapter.

        Args:
            name: Unique name for this adapter instance
            base_url: OpenAI API URL (defaults to api.openai.com)
            api_key: OpenAI API key
            organization: OpenAI organization ID
            timeout: Request timeout in seconds
        """
        self._name = name
        self._base_url = (base_url or self.OPENAI_BASE_URL).rstrip("/")
        self._api_key = api_key
        self._organization = organization
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._connected = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def gateway_type(self) -> str:
        return "openai"

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
            GatewayCapability.IMAGES,
            GatewayCapability.AUDIO,
        }

    @property
    def is_connected(self) -> bool:
        return self._connected and self._client is not None

    async def connect(self) -> None:
        """Initialize HTTP client for OpenAI."""
        if self._client is not None:
            return

        if not self._api_key:
            raise GatewayAuthenticationError(
                "API key required",
                gateway=self._name
            )

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

        if self._organization:
            headers["OpenAI-Organization"] = self._organization

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=self._timeout,
        )

        self._connected = True
        logger.info(f"Connected to OpenAI at {self._base_url}")

    async def disconnect(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
            self._connected = False
            logger.info("Disconnected from OpenAI")

    async def chat_completion(self, request: ChatRequest) -> ChatResponse:
        """Create a chat completion via OpenAI API."""
        if not self._client:
            await self.connect()

        try:
            response = await self._client.post(
                "/chat/completions",
                json=request.to_openai_format(),
            )

            self._check_response_errors(response)

            data = response.json()
            return ChatResponse.from_openai(data, gateway=self._name)

        except httpx.RequestError as e:
            raise GatewayConnectionError(str(e), gateway=self._name)

    async def chat_completion_stream(
        self,
        request: ChatRequest
    ) -> AsyncIterator[ChatResponse]:
        """Create a streaming chat completion via OpenAI API."""
        if not self._client:
            await self.connect()

        request_data = request.to_openai_format()
        request_data["stream"] = True

        try:
            async with self._client.stream(
                "POST",
                "/chat/completions",
                json=request_data,
            ) as response:
                self._check_response_errors(response)

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
            retry_after = response.headers.get("Retry-After")
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

    def _parse_stream_chunk(self, chunk: Dict[str, Any]) -> ChatResponse:
        """Parse a streaming chunk into ChatResponse."""
        choices = chunk.get("choices", [{}])
        delta = choices[0].get("delta", {}) if choices else {}

        return ChatResponse.stream_chunk(
            content=delta.get("content"),
            model=chunk.get("model", ""),
            finish_reason=choices[0].get("finish_reason") if choices else None,
            gateway=self._name,
        )

    async def list_models(self) -> List[Dict[str, Any]]:
        """List available OpenAI models."""
        if not self._client:
            await self.connect()

        try:
            response = await self._client.get("/models")

            if response.status_code != 200:
                logger.warning(f"Failed to list models: {response.status_code}")
                return []

            data = response.json()
            return data.get("data", [])

        except httpx.RequestError as e:
            logger.error(f"Failed to list models: {e}")
            return []

    async def health_check(self) -> Dict[str, Any]:
        """Check OpenAI API health by listing models."""
        try:
            models = await self.list_models()
            return {
                "healthy": len(models) > 0,
                "model_count": len(models),
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}
