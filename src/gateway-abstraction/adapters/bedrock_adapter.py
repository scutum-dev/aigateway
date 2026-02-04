"""
AWS Bedrock Gateway Adapter.

Provides integration with AWS Bedrock for accessing foundation models
including Claude, Llama, Titan, and others.
"""
import os
import json
from typing import AsyncIterator, Dict, List, Optional, Set, Any
from datetime import datetime

from ..core.interface import AbstractGateway, GatewayCapability
from ..core.errors import GatewayConnectionError, GatewayRequestError
from ..models.request import ChatRequest, Message
from ..models.response import ChatResponse, Usage


class BedrockAdapter(AbstractGateway):
    """
    AWS Bedrock adapter.

    Supports:
    - Claude models (Anthropic on Bedrock)
    - Llama models (Meta on Bedrock)
    - Titan models (Amazon)
    - Mistral models
    - Cohere models
    - AI21 models

    Requires boto3 and valid AWS credentials.
    """

    # Model ID mappings for Bedrock
    MODEL_IDS = {
        # Anthropic Claude
        "claude-3-5-sonnet": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "claude-3-opus": "anthropic.claude-3-opus-20240229-v1:0",
        "claude-3-sonnet": "anthropic.claude-3-sonnet-20240229-v1:0",
        "claude-3-haiku": "anthropic.claude-3-haiku-20240307-v1:0",
        "claude-instant": "anthropic.claude-instant-v1",
        # Meta Llama
        "llama-3-70b": "meta.llama3-70b-instruct-v1:0",
        "llama-3-8b": "meta.llama3-8b-instruct-v1:0",
        "llama-2-70b": "meta.llama2-70b-chat-v1",
        "llama-2-13b": "meta.llama2-13b-chat-v1",
        # Amazon Titan
        "titan-text-express": "amazon.titan-text-express-v1",
        "titan-text-lite": "amazon.titan-text-lite-v1",
        "titan-text-premier": "amazon.titan-text-premier-v1:0",
        # Mistral
        "mistral-7b": "mistral.mistral-7b-instruct-v0:2",
        "mistral-large": "mistral.mistral-large-2402-v1:0",
        "mixtral-8x7b": "mistral.mixtral-8x7b-instruct-v0:1",
        # Cohere
        "cohere-command": "cohere.command-text-v14",
        "cohere-command-r": "cohere.command-r-v1:0",
        "cohere-command-r-plus": "cohere.command-r-plus-v1:0",
        # AI21
        "jurassic-2-ultra": "ai21.j2-ultra-v1",
        "jurassic-2-mid": "ai21.j2-mid-v1",
    }

    def __init__(
        self,
        name: str,
        region: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None,
        profile_name: Optional[str] = None,
        timeout: float = 60.0,
        max_retries: int = 3,
    ):
        """
        Initialize AWS Bedrock adapter.

        Args:
            name: Unique identifier for this gateway instance
            region: AWS region (defaults to AWS_DEFAULT_REGION or us-east-1)
            aws_access_key_id: AWS access key (optional, uses boto3 credential chain)
            aws_secret_access_key: AWS secret key (optional)
            aws_session_token: AWS session token (optional)
            profile_name: AWS profile name (optional)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries
        """
        self._name = name
        self._region = region or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        self._aws_access_key_id = aws_access_key_id
        self._aws_secret_access_key = aws_secret_access_key
        self._aws_session_token = aws_session_token
        self._profile_name = profile_name
        self._timeout = timeout
        self._max_retries = max_retries
        self._client = None
        self._runtime_client = None
        self._connected = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def gateway_type(self) -> str:
        return "bedrock"

    @property
    def capabilities(self) -> Set[GatewayCapability]:
        return {
            GatewayCapability.CHAT_COMPLETION,
            GatewayCapability.STREAMING,
            GatewayCapability.EMBEDDINGS,
            GatewayCapability.IMAGES,
        }

    @property
    def is_connected(self) -> bool:
        return self._connected and self._runtime_client is not None

    def _get_model_id(self, model: str) -> str:
        """Get Bedrock model ID from model name."""
        return self.MODEL_IDS.get(model, model)

    def _get_provider(self, model_id: str) -> str:
        """Determine provider from model ID."""
        if model_id.startswith("anthropic."):
            return "anthropic"
        elif model_id.startswith("meta."):
            return "meta"
        elif model_id.startswith("amazon."):
            return "amazon"
        elif model_id.startswith("mistral."):
            return "mistral"
        elif model_id.startswith("cohere."):
            return "cohere"
        elif model_id.startswith("ai21."):
            return "ai21"
        return "unknown"

    async def connect(self) -> None:
        """Establish connection to AWS Bedrock."""
        try:
            import boto3
            from botocore.config import Config

            config = Config(
                read_timeout=self._timeout,
                retries={"max_attempts": self._max_retries},
            )

            session_kwargs = {}
            if self._profile_name:
                session_kwargs["profile_name"] = self._profile_name

            session = boto3.Session(**session_kwargs)

            client_kwargs = {
                "region_name": self._region,
                "config": config,
            }

            if self._aws_access_key_id and self._aws_secret_access_key:
                client_kwargs["aws_access_key_id"] = self._aws_access_key_id
                client_kwargs["aws_secret_access_key"] = self._aws_secret_access_key
                if self._aws_session_token:
                    client_kwargs["aws_session_token"] = self._aws_session_token

            self._client = session.client("bedrock", **client_kwargs)
            self._runtime_client = session.client("bedrock-runtime", **client_kwargs)
            self._connected = True

        except ImportError:
            raise GatewayConnectionError(
                "bedrock",
                "boto3 is required for Bedrock adapter. Install with: pip install boto3"
            )
        except Exception as e:
            raise GatewayConnectionError("bedrock", str(e))

    async def disconnect(self) -> None:
        """Close connection."""
        self._client = None
        self._runtime_client = None
        self._connected = False

    async def health_check(self) -> Dict[str, Any]:
        """Check Bedrock service health."""
        if not self._client:
            await self.connect()

        try:
            # List foundation models to verify access
            response = self._client.list_foundation_models()
            model_count = len(response.get("modelSummaries", []))

            return {
                "status": "healthy",
                "gateway": self._name,
                "region": self._region,
                "models_available": model_count,
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "gateway": self._name,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    def _build_anthropic_payload(
        self, request: ChatRequest, model_id: str
    ) -> Dict[str, Any]:
        """Build payload for Anthropic Claude models."""
        system_message = None
        messages = []

        for msg in request.messages:
            if msg.role == "system":
                system_message = msg.content
            else:
                messages.append({
                    "role": msg.role,
                    "content": msg.content,
                })

        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "messages": messages,
            "max_tokens": request.max_tokens or 4096,
        }

        if system_message:
            payload["system"] = system_message
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        if request.stop:
            payload["stop_sequences"] = request.stop

        return payload

    def _build_meta_payload(
        self, request: ChatRequest, model_id: str
    ) -> Dict[str, Any]:
        """Build payload for Meta Llama models."""
        # Build prompt from messages
        prompt_parts = []
        for msg in request.messages:
            if msg.role == "system":
                prompt_parts.append(f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n{msg.content}<|eot_id|>")
            elif msg.role == "user":
                prompt_parts.append(f"<|start_header_id|>user<|end_header_id|>\n{msg.content}<|eot_id|>")
            elif msg.role == "assistant":
                prompt_parts.append(f"<|start_header_id|>assistant<|end_header_id|>\n{msg.content}<|eot_id|>")

        prompt_parts.append("<|start_header_id|>assistant<|end_header_id|>")
        prompt = "\n".join(prompt_parts)

        payload = {
            "prompt": prompt,
            "max_gen_len": request.max_tokens or 2048,
        }

        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.top_p is not None:
            payload["top_p"] = request.top_p

        return payload

    def _build_titan_payload(
        self, request: ChatRequest, model_id: str
    ) -> Dict[str, Any]:
        """Build payload for Amazon Titan models."""
        # Convert messages to text
        text_parts = []
        for msg in request.messages:
            prefix = "User: " if msg.role == "user" else "Assistant: "
            text_parts.append(f"{prefix}{msg.content}")

        input_text = "\n".join(text_parts)

        payload = {
            "inputText": input_text,
            "textGenerationConfig": {
                "maxTokenCount": request.max_tokens or 4096,
            },
        }

        if request.temperature is not None:
            payload["textGenerationConfig"]["temperature"] = request.temperature
        if request.top_p is not None:
            payload["textGenerationConfig"]["topP"] = request.top_p
        if request.stop:
            payload["textGenerationConfig"]["stopSequences"] = request.stop

        return payload

    def _build_payload(
        self, request: ChatRequest, model_id: str
    ) -> Dict[str, Any]:
        """Build model-specific payload."""
        provider = self._get_provider(model_id)

        if provider == "anthropic":
            return self._build_anthropic_payload(request, model_id)
        elif provider == "meta":
            return self._build_meta_payload(request, model_id)
        elif provider == "amazon":
            return self._build_titan_payload(request, model_id)
        else:
            # Generic payload for other providers
            return self._build_anthropic_payload(request, model_id)

    def _parse_response(
        self, response_body: Dict[str, Any], model_id: str, model: str
    ) -> ChatResponse:
        """Parse Bedrock response based on provider."""
        provider = self._get_provider(model_id)

        if provider == "anthropic":
            content_blocks = response_body.get("content", [])
            content = ""
            for block in content_blocks:
                if block.get("type") == "text":
                    content += block.get("text", "")

            usage = response_body.get("usage", {})
            return ChatResponse(
                id=response_body.get("id", ""),
                model=model,
                content=content,
                role="assistant",
                finish_reason=response_body.get("stop_reason"),
                usage=Usage(
                    prompt_tokens=usage.get("input_tokens", 0),
                    completion_tokens=usage.get("output_tokens", 0),
                    total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                ),
                raw_response=response_body,
            )

        elif provider == "meta":
            return ChatResponse(
                id="",
                model=model,
                content=response_body.get("generation", ""),
                role="assistant",
                finish_reason=response_body.get("stop_reason"),
                usage=Usage(
                    prompt_tokens=response_body.get("prompt_token_count", 0),
                    completion_tokens=response_body.get("generation_token_count", 0),
                    total_tokens=(
                        response_body.get("prompt_token_count", 0) +
                        response_body.get("generation_token_count", 0)
                    ),
                ),
                raw_response=response_body,
            )

        elif provider == "amazon":
            results = response_body.get("results", [{}])
            content = results[0].get("outputText", "") if results else ""

            return ChatResponse(
                id="",
                model=model,
                content=content,
                role="assistant",
                finish_reason=results[0].get("completionReason") if results else None,
                usage=Usage(
                    prompt_tokens=response_body.get("inputTextTokenCount", 0),
                    completion_tokens=results[0].get("tokenCount", 0) if results else 0,
                    total_tokens=(
                        response_body.get("inputTextTokenCount", 0) +
                        (results[0].get("tokenCount", 0) if results else 0)
                    ),
                ),
                raw_response=response_body,
            )

        # Fallback
        return ChatResponse(
            id="",
            model=model,
            content=str(response_body),
            role="assistant",
            raw_response=response_body,
        )

    async def chat_completion(self, request: ChatRequest) -> ChatResponse:
        """Execute chat completion request."""
        if not self._runtime_client:
            await self.connect()

        model_id = self._get_model_id(request.model)
        payload = self._build_payload(request, model_id)

        try:
            response = self._runtime_client.invoke_model(
                modelId=model_id,
                body=json.dumps(payload),
                contentType="application/json",
                accept="application/json",
            )

            response_body = json.loads(response["body"].read())
            return self._parse_response(response_body, model_id, request.model)

        except self._runtime_client.exceptions.ValidationException as e:
            raise GatewayRequestError(self._name, f"Validation error: {e}")
        except self._runtime_client.exceptions.ModelNotReadyException as e:
            raise GatewayRequestError(self._name, f"Model not ready: {e}")
        except self._runtime_client.exceptions.ThrottlingException as e:
            raise GatewayRequestError(self._name, f"Throttled: {e}")
        except Exception as e:
            raise GatewayRequestError(self._name, str(e))

    async def chat_completion_stream(
        self, request: ChatRequest
    ) -> AsyncIterator[ChatResponse]:
        """Execute streaming chat completion request."""
        if not self._runtime_client:
            await self.connect()

        model_id = self._get_model_id(request.model)
        payload = self._build_payload(request, model_id)
        provider = self._get_provider(model_id)

        try:
            response = self._runtime_client.invoke_model_with_response_stream(
                modelId=model_id,
                body=json.dumps(payload),
                contentType="application/json",
                accept="application/json",
            )

            stream = response.get("body")
            if stream:
                for event in stream:
                    chunk = event.get("chunk")
                    if chunk:
                        chunk_data = json.loads(chunk.get("bytes").decode())

                        if provider == "anthropic":
                            if chunk_data.get("type") == "content_block_delta":
                                delta = chunk_data.get("delta", {})
                                yield ChatResponse(
                                    id="",
                                    model=request.model,
                                    content=delta.get("text", ""),
                                    role="assistant",
                                    is_stream_chunk=True,
                                )
                        else:
                            # Generic handling
                            yield ChatResponse(
                                id="",
                                model=request.model,
                                content=str(chunk_data),
                                role="assistant",
                                is_stream_chunk=True,
                            )

        except Exception as e:
            raise GatewayRequestError(self._name, f"Stream error: {e}")

    async def list_models(self) -> List[Dict[str, Any]]:
        """List available Bedrock foundation models."""
        if not self._client:
            await self.connect()

        try:
            response = self._client.list_foundation_models()
            return [
                {
                    "id": model.get("modelId"),
                    "name": model.get("modelName"),
                    "provider": model.get("providerName"),
                    "input_modalities": model.get("inputModalities", []),
                    "output_modalities": model.get("outputModalities", []),
                    "streaming_supported": model.get("responseStreamingSupported", False),
                }
                for model in response.get("modelSummaries", [])
            ]
        except Exception:
            return []

    def has_capability(self, capability: GatewayCapability) -> bool:
        """Check if gateway has a specific capability."""
        return capability in self.capabilities
