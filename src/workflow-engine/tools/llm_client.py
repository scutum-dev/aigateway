"""
LLM client wrapper for LiteLLM integration.
"""

import logging
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Async HTTP client for LiteLLM proxy.

    Provides a simple interface for LLM calls within workflows.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:4000",
        api_key: str = "$LITELLM_KEY",
        timeout: float = 60.0,
    ):
        """
        Initialize LLM client.

        Args:
            base_url: LiteLLM proxy URL
            api_key: API key for authentication
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def post(self, path: str, json: Dict[str, Any]) -> httpx.Response:
        """
        Make a POST request.

        Args:
            path: API path
            json: JSON body

        Returns:
            HTTP response
        """
        client = await self._get_client()
        return await client.post(path, json=json)

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Create a chat completion.

        Args:
            messages: List of message dicts
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum output tokens
            **kwargs: Additional parameters

        Returns:
            Completion response dict
        """
        client = await self._get_client()

        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                **kwargs,
            },
        )

        if response.status_code != 200:
            raise Exception(f"LLM call failed: {response.status_code} - {response.text}")

        return response.json()

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Create a streaming chat completion.

        Args:
            messages: List of message dicts
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum output tokens
            **kwargs: Additional parameters

        Yields:
            Streaming response chunks
        """
        client = await self._get_client()

        async with client.stream(
            "POST",
            "/v1/chat/completions",
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
                **kwargs,
            },
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        import json

                        yield json.loads(data)
                    except Exception:
                        continue

    async def get_models(self) -> List[Dict[str, Any]]:
        """Get available models."""
        client = await self._get_client()
        response = await client.get("/v1/models")

        if response.status_code != 200:
            raise Exception(f"Failed to get models: {response.status_code}")

        return response.json().get("data", [])
