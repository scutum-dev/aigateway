"""
Google Vertex AI Gateway Adapter.

Provides integration with Google Cloud Vertex AI for accessing
Gemini models and other Google AI models.
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


class VertexAIAdapter(AbstractGateway):
    """
    Google Vertex AI adapter.

    Supports:
    - Gemini 1.5 Pro, Flash
    - Gemini 1.0 Pro
    - PaLM 2 (text-bison, chat-bison)
    - Claude on Vertex AI (Model Garden)

    Authentication via Google Cloud credentials or service account.
    """

    # Model mappings
    MODEL_IDS = {
        # Gemini models
        "gemini-1.5-pro": "gemini-1.5-pro-002",
        "gemini-1.5-flash": "gemini-1.5-flash-002",
        "gemini-1.0-pro": "gemini-1.0-pro-002",
        "gemini-pro": "gemini-1.0-pro-002",
        "gemini-pro-vision": "gemini-1.0-pro-vision-001",
        # PaLM models (legacy)
        "text-bison": "text-bison@002",
        "chat-bison": "chat-bison@002",
        # Claude via Model Garden
        "claude-3-5-sonnet-vertex": "claude-3-5-sonnet@20241022",
        "claude-3-opus-vertex": "claude-3-opus@20240229",
        "claude-3-sonnet-vertex": "claude-3-sonnet@20240229",
        "claude-3-haiku-vertex": "claude-3-haiku@20240307",
    }

    def __init__(
        self,
        name: str,
        project_id: Optional[str] = None,
        location: str = "us-central1",
        credentials_path: Optional[str] = None,
        access_token: Optional[str] = None,
        timeout: float = 60.0,
        max_retries: int = 3,
    ):
        """
        Initialize Vertex AI adapter.

        Args:
            name: Unique identifier for this gateway instance
            project_id: Google Cloud project ID
            location: Vertex AI location (default: us-central1)
            credentials_path: Path to service account JSON file
            access_token: Pre-obtained access token (optional)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries
        """
        self._name = name
        self._project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
        self._location = location
        self._credentials_path = credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        self._access_token = access_token
        self._timeout = timeout
        self._max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None
        self._connected = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def gateway_type(self) -> str:
        return "vertex_ai"

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

    async def _get_access_token(self) -> str:
        """Get access token from credentials or use provided token."""
        if self._access_token:
            return self._access_token

        try:
            from google.auth import default
            from google.auth.transport.requests import Request

            credentials, project = default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            credentials.refresh(Request())

            if not self._project_id:
                self._project_id = project

            return credentials.token

        except ImportError:
            raise GatewayConnectionError(
                "vertex_ai",
                "google-auth is required. Install with: pip install google-auth"
            )
        except Exception as e:
            raise GatewayConnectionError("vertex_ai", f"Authentication error: {e}")

    def _get_model_id(self, model: str) -> str:
        """Get Vertex AI model ID from model name."""
        return self.MODEL_IDS.get(model, model)

    def _get_base_url(self) -> str:
        """Get Vertex AI API base URL."""
        return f"https://{self._location}-aiplatform.googleapis.com/v1"

    def _get_model_endpoint(self, model_id: str) -> str:
        """Get full model endpoint URL."""
        return (
            f"{self._get_base_url()}/projects/{self._project_id}/"
            f"locations/{self._location}/publishers/google/models/{model_id}"
        )

    async def connect(self) -> None:
        """Establish connection to Vertex AI."""
        token = await self._get_access_token()

        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self._timeout),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        self._connected = True

    async def disconnect(self) -> None:
        """Close connection."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._connected = False

    async def health_check(self) -> Dict[str, Any]:
        """Check Vertex AI service health."""
        if not self._client:
            await self.connect()

        try:
            # Test with a simple model info request
            url = f"{self._get_base_url()}/projects/{self._project_id}/locations/{self._location}/publishers/google/models"
            response = await self._client.get(url)

            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "gateway": self._name,
                    "project": self._project_id,
                    "location": self._location,
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

    def _build_gemini_payload(self, request: ChatRequest) -> Dict[str, Any]:
        """Build payload for Gemini models."""
        contents = []
        system_instruction = None

        for msg in request.messages:
            if msg.role == "system":
                system_instruction = {"parts": [{"text": msg.content}]}
            else:
                role = "user" if msg.role == "user" else "model"
                contents.append({
                    "role": role,
                    "parts": [{"text": msg.content}],
                })

        payload = {
            "contents": contents,
            "generationConfig": {},
        }

        if system_instruction:
            payload["systemInstruction"] = system_instruction

        if request.temperature is not None:
            payload["generationConfig"]["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["generationConfig"]["maxOutputTokens"] = request.max_tokens
        if request.top_p is not None:
            payload["generationConfig"]["topP"] = request.top_p
        if request.stop:
            payload["generationConfig"]["stopSequences"] = request.stop

        if request.tools:
            payload["tools"] = [{"functionDeclarations": request.tools}]

        return payload

    def _parse_gemini_response(
        self, data: Dict[str, Any], model: str
    ) -> ChatResponse:
        """Parse Gemini response."""
        candidates = data.get("candidates", [])
        if not candidates:
            raise GatewayRequestError(self._name, "No candidates in response")

        candidate = candidates[0]
        content = candidate.get("content", {})
        parts = content.get("parts", [])

        text_content = ""
        tool_calls = []

        for part in parts:
            if "text" in part:
                text_content += part["text"]
            elif "functionCall" in part:
                tool_calls.append(part["functionCall"])

        usage_metadata = data.get("usageMetadata", {})

        return ChatResponse(
            id=data.get("responseId", ""),
            model=model,
            content=text_content,
            role="assistant",
            finish_reason=candidate.get("finishReason"),
            tool_calls=tool_calls if tool_calls else None,
            usage=Usage(
                prompt_tokens=usage_metadata.get("promptTokenCount", 0),
                completion_tokens=usage_metadata.get("candidatesTokenCount", 0),
                total_tokens=usage_metadata.get("totalTokenCount", 0),
            ),
            raw_response=data,
        )

    async def chat_completion(self, request: ChatRequest) -> ChatResponse:
        """Execute chat completion request."""
        if not self._client:
            await self.connect()

        model_id = self._get_model_id(request.model)
        endpoint = self._get_model_endpoint(model_id)
        url = f"{endpoint}:generateContent"

        payload = self._build_gemini_payload(request)

        try:
            response = await self._client.post(url, json=payload)

            if response.status_code != 200:
                error_body = response.text
                raise GatewayRequestError(
                    self._name,
                    f"Vertex AI error: {response.status_code} - {error_body}"
                )

            data = response.json()
            return self._parse_gemini_response(data, request.model)

        except httpx.TimeoutException:
            raise GatewayConnectionError(
                self._get_base_url(),
                "Request timed out"
            )
        except httpx.RequestError as e:
            raise GatewayConnectionError(
                self._get_base_url(),
                str(e)
            )

    async def chat_completion_stream(
        self, request: ChatRequest
    ) -> AsyncIterator[ChatResponse]:
        """Execute streaming chat completion request."""
        if not self._client:
            await self.connect()

        model_id = self._get_model_id(request.model)
        endpoint = self._get_model_endpoint(model_id)
        url = f"{endpoint}:streamGenerateContent"

        payload = self._build_gemini_payload(request)

        try:
            async with self._client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    raise GatewayRequestError(
                        self._name,
                        f"Vertex AI error: {response.status_code} - {error_body.decode()}"
                    )

                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk

                    # Parse JSON array elements
                    while True:
                        # Try to find complete JSON objects
                        try:
                            # Handle streaming response format
                            if buffer.startswith("["):
                                buffer = buffer[1:]
                            if buffer.startswith(","):
                                buffer = buffer[1:]
                            if buffer.startswith("]"):
                                break

                            # Try to parse JSON object
                            decoder = json.JSONDecoder()
                            obj, idx = decoder.raw_decode(buffer.strip())
                            buffer = buffer[idx:].strip()

                            candidates = obj.get("candidates", [])
                            if candidates:
                                content = candidates[0].get("content", {})
                                parts = content.get("parts", [])
                                for part in parts:
                                    if "text" in part:
                                        yield ChatResponse(
                                            id="",
                                            model=request.model,
                                            content=part["text"],
                                            role="assistant",
                                            is_stream_chunk=True,
                                        )
                        except (json.JSONDecodeError, ValueError):
                            break

        except httpx.TimeoutException:
            raise GatewayConnectionError(
                self._get_base_url(),
                "Stream request timed out"
            )

    async def list_models(self) -> List[Dict[str, Any]]:
        """List available Vertex AI models."""
        if not self._client:
            await self.connect()

        try:
            url = (
                f"{self._get_base_url()}/projects/{self._project_id}/"
                f"locations/{self._location}/publishers/google/models"
            )
            response = await self._client.get(url)

            if response.status_code == 200:
                data = response.json()
                return [
                    {
                        "id": model.get("name", "").split("/")[-1],
                        "display_name": model.get("displayName"),
                        "description": model.get("description"),
                        "supported_actions": model.get("supportedActions", []),
                    }
                    for model in data.get("models", [])
                ]
            return []
        except Exception:
            return []

    async def generate_embeddings(
        self,
        texts: List[str],
        model: str = "text-embedding-004",
    ) -> List[List[float]]:
        """Generate embeddings for texts."""
        if not self._client:
            await self.connect()

        model_id = self._get_model_id(model)
        endpoint = self._get_model_endpoint(model_id)
        url = f"{endpoint}:predict"

        payload = {
            "instances": [{"content": text} for text in texts],
        }

        response = await self._client.post(url, json=payload)

        if response.status_code == 200:
            data = response.json()
            predictions = data.get("predictions", [])
            return [pred.get("embeddings", {}).get("values", []) for pred in predictions]

        raise GatewayRequestError(
            self._name,
            f"Embedding error: {response.status_code} - {response.text}"
        )

    def has_capability(self, capability: GatewayCapability) -> bool:
        """Check if gateway has a specific capability."""
        return capability in self.capabilities
