"""
Ollama Gateway Adapter.

Provides integration with local Ollama server for running
open-source models like Llama, Mistral, CodeLlama, etc.
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


class OllamaAdapter(AbstractGateway):
    """
    Ollama adapter for local LLM inference.

    Supports all models available in Ollama:
    - Llama 3.1, 3.2
    - Mistral, Mixtral
    - CodeLlama
    - Phi-3
    - Gemma
    - Qwen
    - DeepSeek
    - And many more

    Features:
    - Local inference (no API keys required)
    - Model pulling and management
    - GPU acceleration when available
    - Streaming responses
    """

    def __init__(
        self,
        name: str,
        base_url: Optional[str] = None,
        timeout: float = 120.0,
        keep_alive: str = "5m",
        num_ctx: Optional[int] = None,
        num_gpu: Optional[int] = None,
    ):
        """
        Initialize Ollama adapter.

        Args:
            name: Unique identifier for this gateway instance
            base_url: Ollama server URL (default: http://localhost:11434)
            timeout: Request timeout in seconds (longer for local inference)
            keep_alive: How long to keep model loaded (e.g., "5m", "1h")
            num_ctx: Context window size override
            num_gpu: Number of GPU layers to use
        """
        self._name = name
        self._base_url = (base_url or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self._timeout = timeout
        self._keep_alive = keep_alive
        self._num_ctx = num_ctx
        self._num_gpu = num_gpu
        self._client: Optional[httpx.AsyncClient] = None
        self._connected = False
        self._available_models: List[str] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def gateway_type(self) -> str:
        return "ollama"

    @property
    def capabilities(self) -> Set[GatewayCapability]:
        return {
            GatewayCapability.CHAT_COMPLETION,
            GatewayCapability.STREAMING,
            GatewayCapability.EMBEDDINGS,
            GatewayCapability.VISION,  # For multimodal models like llava
        }

    @property
    def is_connected(self) -> bool:
        return self._connected and self._client is not None

    async def connect(self) -> None:
        """Establish connection to Ollama server."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self._timeout),
            headers={"Content-Type": "application/json"},
        )

        # Verify connection
        try:
            response = await self._client.get(f"{self._base_url}/api/tags")
            if response.status_code == 200:
                self._connected = True
                data = response.json()
                self._available_models = [
                    m.get("name") for m in data.get("models", [])
                ]
            else:
                raise GatewayConnectionError(
                    self._base_url,
                    f"Ollama returned status {response.status_code}"
                )
        except httpx.RequestError as e:
            raise GatewayConnectionError(
                self._base_url,
                f"Cannot connect to Ollama: {e}"
            )

    async def disconnect(self) -> None:
        """Close connection."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._connected = False

    async def health_check(self) -> Dict[str, Any]:
        """Check Ollama server health."""
        if not self._client:
            await self.connect()

        try:
            response = await self._client.get(f"{self._base_url}/api/tags")

            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                return {
                    "status": "healthy",
                    "gateway": self._name,
                    "base_url": self._base_url,
                    "models_loaded": len(models),
                    "model_names": [m.get("name") for m in models[:10]],
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

    def _build_options(self, request: ChatRequest) -> Dict[str, Any]:
        """Build Ollama options from request."""
        options = {}

        if request.temperature is not None:
            options["temperature"] = request.temperature
        if request.top_p is not None:
            options["top_p"] = request.top_p
        if request.max_tokens is not None:
            options["num_predict"] = request.max_tokens
        if self._num_ctx is not None:
            options["num_ctx"] = self._num_ctx
        if self._num_gpu is not None:
            options["num_gpu"] = self._num_gpu
        if request.stop:
            options["stop"] = request.stop

        # Additional Ollama-specific options
        if hasattr(request, "seed") and request.seed is not None:
            options["seed"] = request.seed
        if hasattr(request, "repeat_penalty") and request.repeat_penalty is not None:
            options["repeat_penalty"] = request.repeat_penalty

        return options

    async def chat_completion(self, request: ChatRequest) -> ChatResponse:
        """Execute chat completion request."""
        if not self._client:
            await self.connect()

        # Build messages
        messages = []
        for msg in request.messages:
            message = {
                "role": msg.role,
                "content": msg.content,
            }
            # Handle images for multimodal models
            if hasattr(msg, "images") and msg.images:
                message["images"] = msg.images
            messages.append(message)

        payload = {
            "model": request.model,
            "messages": messages,
            "stream": False,
            "options": self._build_options(request),
        }

        if self._keep_alive:
            payload["keep_alive"] = self._keep_alive

        try:
            response = await self._client.post(
                f"{self._base_url}/api/chat",
                json=payload,
            )

            if response.status_code != 200:
                error_body = response.text
                raise GatewayRequestError(
                    self._name,
                    f"Ollama error: {response.status_code} - {error_body}"
                )

            data = response.json()
            return self._parse_response(data, request.model)

        except httpx.TimeoutException:
            raise GatewayConnectionError(
                self._base_url,
                "Request timed out - model may be loading"
            )
        except httpx.RequestError as e:
            raise GatewayConnectionError(
                self._base_url,
                str(e)
            )

    async def chat_completion_stream(
        self, request: ChatRequest
    ) -> AsyncIterator[ChatResponse]:
        """Execute streaming chat completion request."""
        if not self._client:
            await self.connect()

        messages = []
        for msg in request.messages:
            message = {
                "role": msg.role,
                "content": msg.content,
            }
            if hasattr(msg, "images") and msg.images:
                message["images"] = msg.images
            messages.append(message)

        payload = {
            "model": request.model,
            "messages": messages,
            "stream": True,
            "options": self._build_options(request),
        }

        if self._keep_alive:
            payload["keep_alive"] = self._keep_alive

        try:
            async with self._client.stream(
                "POST",
                f"{self._base_url}/api/chat",
                json=payload,
            ) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    raise GatewayRequestError(
                        self._name,
                        f"Ollama error: {response.status_code} - {error_body.decode()}"
                    )

                async for line in response.aiter_lines():
                    if line:
                        try:
                            chunk = json.loads(line)
                            yield self._parse_stream_chunk(chunk, request.model)

                            # Check if done
                            if chunk.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue

        except httpx.TimeoutException:
            raise GatewayConnectionError(
                self._base_url,
                "Stream request timed out"
            )

    async def list_models(self) -> List[Dict[str, Any]]:
        """List available Ollama models."""
        if not self._client:
            await self.connect()

        try:
            response = await self._client.get(f"{self._base_url}/api/tags")

            if response.status_code == 200:
                data = response.json()
                return [
                    {
                        "id": model.get("name"),
                        "name": model.get("name"),
                        "size": model.get("size"),
                        "modified_at": model.get("modified_at"),
                        "digest": model.get("digest"),
                        "details": model.get("details", {}),
                    }
                    for model in data.get("models", [])
                ]
            return []
        except Exception:
            return []

    async def pull_model(self, model: str, stream: bool = True) -> AsyncIterator[Dict[str, Any]]:
        """
        Pull a model from Ollama library.

        Args:
            model: Model name to pull (e.g., "llama3.1:8b")
            stream: Stream progress updates

        Yields:
            Progress updates during download
        """
        if not self._client:
            await self.connect()

        payload = {
            "name": model,
            "stream": stream,
        }

        if stream:
            async with self._client.stream(
                "POST",
                f"{self._base_url}/api/pull",
                json=payload,
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            continue
        else:
            response = await self._client.post(
                f"{self._base_url}/api/pull",
                json=payload,
            )
            if response.status_code == 200:
                yield response.json()

    async def delete_model(self, model: str) -> bool:
        """Delete a model from Ollama."""
        if not self._client:
            await self.connect()

        response = await self._client.delete(
            f"{self._base_url}/api/delete",
            json={"name": model},
        )
        return response.status_code == 200

    async def show_model_info(self, model: str) -> Dict[str, Any]:
        """Get detailed information about a model."""
        if not self._client:
            await self.connect()

        response = await self._client.post(
            f"{self._base_url}/api/show",
            json={"name": model},
        )

        if response.status_code == 200:
            return response.json()
        return {}

    async def generate_embeddings(
        self,
        texts: List[str],
        model: str = "nomic-embed-text",
    ) -> List[List[float]]:
        """Generate embeddings for texts."""
        if not self._client:
            await self.connect()

        embeddings = []
        for text in texts:
            response = await self._client.post(
                f"{self._base_url}/api/embeddings",
                json={
                    "model": model,
                    "prompt": text,
                },
            )

            if response.status_code == 200:
                data = response.json()
                embeddings.append(data.get("embedding", []))
            else:
                embeddings.append([])

        return embeddings

    def _parse_response(self, data: Dict[str, Any], model: str) -> ChatResponse:
        """Parse Ollama response to ChatResponse."""
        message = data.get("message", {})

        # Calculate token usage
        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)

        return ChatResponse(
            id=data.get("created_at", ""),
            model=model,
            content=message.get("content", ""),
            role=message.get("role", "assistant"),
            finish_reason="stop" if data.get("done") else None,
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
            raw_response=data,
        )

    def _parse_stream_chunk(self, chunk: Dict[str, Any], model: str) -> ChatResponse:
        """Parse streaming chunk to ChatResponse."""
        message = chunk.get("message", {})

        # Final chunk includes usage
        usage = None
        if chunk.get("done"):
            prompt_tokens = chunk.get("prompt_eval_count", 0)
            completion_tokens = chunk.get("eval_count", 0)
            usage = Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            )

        return ChatResponse(
            id=chunk.get("created_at", ""),
            model=model,
            content=message.get("content", ""),
            role=message.get("role", "assistant"),
            finish_reason="stop" if chunk.get("done") else None,
            usage=usage,
            is_stream_chunk=True,
        )

    def has_capability(self, capability: GatewayCapability) -> bool:
        """Check if gateway has a specific capability."""
        return capability in self.capabilities

    async def copy_model(self, source: str, destination: str) -> bool:
        """Copy a model with a new name."""
        if not self._client:
            await self.connect()

        response = await self._client.post(
            f"{self._base_url}/api/copy",
            json={"source": source, "destination": destination},
        )
        return response.status_code == 200

    async def create_model(
        self,
        name: str,
        modelfile: str,
        stream: bool = True,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Create a new model from a Modelfile.

        Args:
            name: Name for the new model
            modelfile: Contents of the Modelfile
            stream: Stream progress updates
        """
        if not self._client:
            await self.connect()

        payload = {
            "name": name,
            "modelfile": modelfile,
            "stream": stream,
        }

        if stream:
            async with self._client.stream(
                "POST",
                f"{self._base_url}/api/create",
                json=payload,
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            continue
        else:
            response = await self._client.post(
                f"{self._base_url}/api/create",
                json=payload,
            )
            if response.status_code == 200:
                yield response.json()
