"""
Azure OpenAI Gateway Adapter.

Provides integration with Azure OpenAI Service with support for
deployments, API versions, and Azure-specific authentication.
"""
import os
import json
import httpx
from typing import AsyncIterator, Dict, List, Optional, Set, Any
from datetime import datetime

from ..core.interface import AbstractGateway, GatewayCapability
from ..core.errors import GatewayConnectionError, GatewayRequestError
from ..models.request import ChatRequest
from ..models.response import ChatResponse, Usage


class AzureOpenAIAdapter(AbstractGateway):
    """
    Azure OpenAI Service adapter.

    Supports Azure-specific features:
    - Deployment-based model routing
    - API version management
    - Azure AD authentication (optional)
    - Content filtering integration
    """

    def __init__(
        self,
        name: str,
        endpoint: str,
        api_key: Optional[str] = None,
        api_version: str = "2024-02-15-preview",
        deployment_map: Optional[Dict[str, str]] = None,
        use_azure_ad: bool = False,
        azure_ad_token: Optional[str] = None,
        timeout: float = 60.0,
        max_retries: int = 3,
    ):
        """
        Initialize Azure OpenAI adapter.

        Args:
            name: Unique identifier for this gateway instance
            endpoint: Azure OpenAI endpoint (e.g., https://myresource.openai.azure.com)
            api_key: Azure OpenAI API key
            api_version: API version to use
            deployment_map: Map of model names to Azure deployment names
            use_azure_ad: Use Azure AD authentication instead of API key
            azure_ad_token: Azure AD token (if use_azure_ad is True)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries
        """
        self._name = name
        self._endpoint = endpoint.rstrip("/")
        self._api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
        self._api_version = api_version
        self._deployment_map = deployment_map or {}
        self._use_azure_ad = use_azure_ad
        self._azure_ad_token = azure_ad_token
        self._timeout = timeout
        self._max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None
        self._connected = False
        self._available_deployments: List[str] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def gateway_type(self) -> str:
        return "azure_openai"

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
        }

    @property
    def is_connected(self) -> bool:
        return self._connected and self._client is not None

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        headers = {
            "Content-Type": "application/json",
        }
        if self._use_azure_ad and self._azure_ad_token:
            headers["Authorization"] = f"Bearer {self._azure_ad_token}"
        else:
            headers["api-key"] = self._api_key
        return headers

    def _get_deployment(self, model: str) -> str:
        """Get Azure deployment name for a model."""
        # Check explicit mapping first
        if model in self._deployment_map:
            return self._deployment_map[model]
        # Fall back to using model name as deployment name
        return model.replace(".", "-").replace("_", "-")

    def _build_url(self, deployment: str, endpoint_type: str = "chat/completions") -> str:
        """Build Azure OpenAI API URL."""
        return (
            f"{self._endpoint}/openai/deployments/{deployment}/"
            f"{endpoint_type}?api-version={self._api_version}"
        )

    async def connect(self) -> None:
        """Establish connection to Azure OpenAI."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
                headers=self._get_headers(),
            )
        self._connected = True

    async def disconnect(self) -> None:
        """Close connection."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._connected = False

    async def health_check(self) -> Dict[str, Any]:
        """Check Azure OpenAI service health."""
        if not self._client:
            await self.connect()

        try:
            # Try to list deployments or make a simple request
            response = await self._client.get(
                f"{self._endpoint}/openai/deployments?api-version={self._api_version}",
                headers=self._get_headers(),
            )

            if response.status_code == 200:
                data = response.json()
                self._available_deployments = [
                    d.get("id") for d in data.get("data", [])
                ]
                return {
                    "status": "healthy",
                    "gateway": self._name,
                    "endpoint": self._endpoint,
                    "api_version": self._api_version,
                    "deployments": len(self._available_deployments),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            else:
                return {
                    "status": "unhealthy",
                    "gateway": self._name,
                    "error": f"HTTP {response.status_code}",
                    "timestamp": datetime.utcnow().isoformat(),
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "gateway": self._name,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def chat_completion(self, request: ChatRequest) -> ChatResponse:
        """Execute chat completion request."""
        if not self._client:
            await self.connect()

        deployment = self._get_deployment(request.model)
        url = self._build_url(deployment)

        # Build request payload
        payload = {
            "messages": [msg.model_dump() for msg in request.messages],
        }

        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        if request.stop:
            payload["stop"] = request.stop
        if request.tools:
            payload["tools"] = request.tools
        if request.response_format:
            payload["response_format"] = request.response_format

        try:
            response = await self._client.post(
                url,
                json=payload,
                headers=self._get_headers(),
            )

            if response.status_code != 200:
                error_body = response.text
                raise GatewayRequestError(
                    self._name,
                    f"Azure OpenAI error: {response.status_code} - {error_body}"
                )

            data = response.json()
            return self._parse_response(data, request.model)

        except httpx.TimeoutException:
            raise GatewayConnectionError(
                self._endpoint,
                "Request timed out"
            )
        except httpx.RequestError as e:
            raise GatewayConnectionError(
                self._endpoint,
                str(e)
            )

    async def chat_completion_stream(
        self, request: ChatRequest
    ) -> AsyncIterator[ChatResponse]:
        """Execute streaming chat completion request."""
        if not self._client:
            await self.connect()

        deployment = self._get_deployment(request.model)
        url = self._build_url(deployment)

        payload = {
            "messages": [msg.model_dump() for msg in request.messages],
            "stream": True,
        }

        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        if request.tools:
            payload["tools"] = request.tools

        try:
            async with self._client.stream(
                "POST",
                url,
                json=payload,
                headers=self._get_headers(),
            ) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    raise GatewayRequestError(
                        self._name,
                        f"Azure OpenAI error: {response.status_code} - {error_body.decode()}"
                    )

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            yield self._parse_stream_chunk(chunk, request.model)
                        except json.JSONDecodeError:
                            continue

        except httpx.TimeoutException:
            raise GatewayConnectionError(
                self._endpoint,
                "Stream request timed out"
            )

    async def list_models(self) -> List[Dict[str, Any]]:
        """List available Azure OpenAI deployments."""
        if not self._client:
            await self.connect()

        try:
            response = await self._client.get(
                f"{self._endpoint}/openai/deployments?api-version={self._api_version}",
                headers=self._get_headers(),
            )

            if response.status_code == 200:
                data = response.json()
                return [
                    {
                        "id": d.get("id"),
                        "model": d.get("model"),
                        "owner": "azure",
                        "status": d.get("status"),
                        "scale_settings": d.get("scale_settings"),
                    }
                    for d in data.get("data", [])
                ]
            return []
        except Exception:
            return []

    def _parse_response(self, data: Dict[str, Any], model: str) -> ChatResponse:
        """Parse Azure OpenAI response to ChatResponse."""
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        usage_data = data.get("usage", {})

        return ChatResponse(
            id=data.get("id", ""),
            model=model,
            content=message.get("content", ""),
            role=message.get("role", "assistant"),
            finish_reason=choice.get("finish_reason"),
            tool_calls=message.get("tool_calls"),
            usage=Usage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            ),
            raw_response=data,
        )

    def _parse_stream_chunk(self, chunk: Dict[str, Any], model: str) -> ChatResponse:
        """Parse streaming chunk to ChatResponse."""
        choice = chunk.get("choices", [{}])[0]
        delta = choice.get("delta", {})

        return ChatResponse(
            id=chunk.get("id", ""),
            model=model,
            content=delta.get("content", ""),
            role=delta.get("role", "assistant"),
            finish_reason=choice.get("finish_reason"),
            tool_calls=delta.get("tool_calls"),
            usage=None,
            is_stream_chunk=True,
        )

    def has_capability(self, capability: GatewayCapability) -> bool:
        """Check if gateway has a specific capability."""
        return capability in self.capabilities

    def set_deployment_map(self, deployment_map: Dict[str, str]) -> None:
        """Update the model to deployment mapping."""
        self._deployment_map = deployment_map

    def add_deployment_mapping(self, model: str, deployment: str) -> None:
        """Add a single model to deployment mapping."""
        self._deployment_map[model] = deployment
