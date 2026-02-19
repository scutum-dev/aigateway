"""
Integration tests for Gateway Abstraction Layer.

Tests gateway adapters, plugin registry, routing,
and unified request/response handling.
"""

import os
import sys

import pytest

# Add the gateway-abstraction module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src/gateway-abstraction"))

from adapters.anthropic_adapter import AnthropicAdapter
from adapters.litellm_adapter import LiteLLMAdapter
from adapters.openai_adapter import OpenAIAdapter
from core.config import GatewayConfig
from core.errors import GatewayConnectionError, GatewayError, GatewayNotFoundError
from core.interface import GatewayCapability
from core.registry import GatewayRegistry
from models.request import ChatRequest, Message
from models.response import ChatResponse, Usage


class TestGatewayRegistry:
    """Test gateway plugin registry."""

    def test_register_gateway(self):
        """Test registering a gateway adapter."""
        registry = GatewayRegistry()
        adapter = LiteLLMAdapter(
            name="test-litellm",
            base_url="http://localhost:4000",
            api_key="test-key",
        )
        registry.register(adapter)
        assert "test-litellm" in registry.list_gateways()

    def test_get_registered_gateway(self):
        """Test getting a registered gateway."""
        registry = GatewayRegistry()
        adapter = LiteLLMAdapter(
            name="test-litellm",
            base_url="http://localhost:4000",
            api_key="test-key",
        )
        registry.register(adapter)

        retrieved = registry.get("test-litellm")
        assert retrieved is not None
        assert retrieved.name == "test-litellm"

    def test_get_nonexistent_gateway(self):
        """Test getting non-existent gateway raises error."""
        registry = GatewayRegistry()
        with pytest.raises(GatewayNotFoundError):
            registry.get("nonexistent")

    def test_unregister_gateway(self):
        """Test unregistering a gateway."""
        registry = GatewayRegistry()
        adapter = LiteLLMAdapter(
            name="test-litellm",
            base_url="http://localhost:4000",
            api_key="test-key",
        )
        registry.register(adapter)
        registry.unregister("test-litellm")
        assert "test-litellm" not in registry.list_gateways()

    def test_register_duplicate_gateway(self):
        """Test registering duplicate gateway name."""
        registry = GatewayRegistry()
        adapter1 = LiteLLMAdapter(
            name="test-litellm",
            base_url="http://localhost:4000",
            api_key="test-key",
        )
        adapter2 = LiteLLMAdapter(
            name="test-litellm",
            base_url="http://localhost:4001",
            api_key="test-key-2",
        )
        registry.register(adapter1)
        # Should either raise or replace
        try:
            registry.register(adapter2)
            # If no error, the gateway should be replaced
            assert registry.get("test-litellm").base_url == "http://localhost:4001"
        except ValueError:
            # Duplicate registration error is also acceptable
            pass

    def test_set_default_gateway(self):
        """Test setting default gateway."""
        registry = GatewayRegistry()
        adapter = LiteLLMAdapter(
            name="test-litellm",
            base_url="http://localhost:4000",
            api_key="test-key",
        )
        registry.register(adapter)
        registry.set_default("test-litellm")
        assert registry.get_default().name == "test-litellm"


class TestChatRequest:
    """Test ChatRequest model."""

    def test_create_request(self):
        """Test creating a chat request."""
        request = ChatRequest(
            model="gpt-4o-mini",
            messages=[
                Message(role="user", content="Hello"),
            ],
        )
        assert request.model == "gpt-4o-mini"
        assert len(request.messages) == 1

    def test_request_to_openai_format(self):
        """Test converting request to OpenAI format."""
        request = ChatRequest(
            model="gpt-4o-mini",
            messages=[
                Message(role="system", content="You are helpful"),
                Message(role="user", content="Hello"),
            ],
            temperature=0.7,
            max_tokens=100,
        )
        openai_format = request.to_openai_format()
        assert openai_format["model"] == "gpt-4o-mini"
        assert len(openai_format["messages"]) == 2
        assert openai_format["temperature"] == 0.7
        assert openai_format["max_tokens"] == 100

    def test_request_to_anthropic_format(self):
        """Test converting request to Anthropic format."""
        request = ChatRequest(
            model="claude-3-haiku",
            messages=[
                Message(role="system", content="You are helpful"),
                Message(role="user", content="Hello"),
            ],
            temperature=0.7,
            max_tokens=100,
        )
        anthropic_format = request.to_anthropic_format()
        assert anthropic_format["model"] == "claude-3-haiku"
        assert anthropic_format["system"] == "You are helpful"
        assert len(anthropic_format["messages"]) == 1  # System extracted
        assert anthropic_format["temperature"] == 0.7
        assert anthropic_format["max_tokens"] == 100

    def test_request_with_stream(self):
        """Test request with streaming enabled."""
        request = ChatRequest(
            model="gpt-4o-mini",
            messages=[Message(role="user", content="Hello")],
            stream=True,
        )
        assert request.stream is True


class TestChatResponse:
    """Test ChatResponse model."""

    def test_create_response(self):
        """Test creating a chat response."""
        response = ChatResponse(
            id="test-id",
            model="gpt-4o-mini",
            content="Hello there!",
            usage=Usage(
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
            ),
        )
        assert response.id == "test-id"
        assert response.content == "Hello there!"
        assert response.usage.total_tokens == 15

    def test_response_from_openai(self):
        """Test creating response from OpenAI format."""
        openai_response = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "model": "gpt-4o-mini",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Hello!",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }
        response = ChatResponse.from_openai(openai_response)
        assert response.id == "chatcmpl-123"
        assert response.content == "Hello!"
        assert response.usage.total_tokens == 15

    def test_response_from_anthropic(self):
        """Test creating response from Anthropic format."""
        anthropic_response = {
            "id": "msg_123",
            "type": "message",
            "model": "claude-3-haiku",
            "content": [
                {"type": "text", "text": "Hello!"},
            ],
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": 10,
                "output_tokens": 5,
            },
        }
        response = ChatResponse.from_anthropic(anthropic_response)
        assert response.id == "msg_123"
        assert response.content == "Hello!"
        assert response.usage.prompt_tokens == 10
        assert response.usage.completion_tokens == 5


class TestLiteLLMAdapter:
    """Test LiteLLM adapter."""

    def test_adapter_name(self):
        """Test adapter has correct name."""
        adapter = LiteLLMAdapter(
            name="litellm-primary",
            base_url="http://localhost:4000",
            api_key="test-key",
        )
        assert adapter.name == "litellm-primary"

    def test_adapter_capabilities(self):
        """Test adapter reports capabilities."""
        adapter = LiteLLMAdapter(
            name="litellm-primary",
            base_url="http://localhost:4000",
            api_key="test-key",
        )
        capabilities = adapter.capabilities
        assert GatewayCapability.CHAT_COMPLETION in capabilities
        assert GatewayCapability.STREAMING in capabilities

    @pytest.mark.asyncio
    async def test_list_models(self):
        """Test listing models from LiteLLM."""
        adapter = LiteLLMAdapter(
            name="litellm-primary",
            base_url="http://localhost:4000",
            api_key=os.getenv("LITELLM_KEY") or os.getenv("LITELLM_MASTER_KEY", ""),
        )
        try:
            models = await adapter.list_models()
            assert isinstance(models, list)
        except GatewayConnectionError:
            pytest.skip("LiteLLM not available")


class TestOpenAIAdapter:
    """Test OpenAI adapter."""

    def test_adapter_name(self):
        """Test adapter has correct name."""
        adapter = OpenAIAdapter(
            name="openai-direct",
            api_key="test-key",
        )
        assert adapter.name == "openai-direct"

    def test_adapter_capabilities(self):
        """Test adapter reports capabilities."""
        adapter = OpenAIAdapter(
            name="openai-direct",
            api_key="test-key",
        )
        capabilities = adapter.capabilities
        assert GatewayCapability.CHAT_COMPLETION in capabilities
        assert GatewayCapability.STREAMING in capabilities
        assert GatewayCapability.FUNCTION_CALLING in capabilities


class TestAnthropicAdapter:
    """Test Anthropic adapter."""

    def test_adapter_name(self):
        """Test adapter has correct name."""
        adapter = AnthropicAdapter(
            name="anthropic-direct",
            api_key="test-key",
        )
        assert adapter.name == "anthropic-direct"

    def test_adapter_capabilities(self):
        """Test adapter reports capabilities."""
        adapter = AnthropicAdapter(
            name="anthropic-direct",
            api_key="test-key",
        )
        capabilities = adapter.capabilities
        assert GatewayCapability.CHAT_COMPLETION in capabilities
        assert GatewayCapability.STREAMING in capabilities


class TestGatewayConfig:
    """Test gateway configuration loading."""

    def test_load_config_from_dict(self):
        """Test loading config from dictionary."""
        config_dict = {
            "default_gateway": "litellm",
            "gateways": [
                {
                    "type": "litellm",
                    "name": "primary-litellm",
                    "base_url": "http://localhost:4000",
                    "api_key": "test-key",
                },
            ],
            "routing": {
                "strategy": "priority",
                "model_routing": {
                    "gpt-*": ["primary-litellm"],
                },
            },
        }
        config = GatewayConfig.from_dict(config_dict)
        assert config.default_gateway == "litellm"
        assert len(config.gateways) == 1
        assert config.gateways[0]["name"] == "primary-litellm"

    def test_config_model_routing(self):
        """Test config model routing rules."""
        config_dict = {
            "default_gateway": "litellm",
            "gateways": [
                {
                    "type": "litellm",
                    "name": "primary-litellm",
                    "base_url": "http://localhost:4000",
                    "api_key": "test-key",
                },
                {
                    "type": "openai",
                    "name": "direct-openai",
                    "api_key": "test-key",
                },
            ],
            "routing": {
                "strategy": "priority",
                "model_routing": {
                    "gpt-*": ["primary-litellm", "direct-openai"],
                    "claude-*": ["primary-litellm"],
                    "*": ["primary-litellm"],
                },
            },
        }
        config = GatewayConfig.from_dict(config_dict)
        assert config.routing["strategy"] == "priority"
        assert "gpt-*" in config.routing["model_routing"]


class TestGatewayErrors:
    """Test gateway error types."""

    def test_gateway_error(self):
        """Test base gateway error."""
        error = GatewayError("Test error")
        assert str(error) == "Test error"

    def test_gateway_not_found_error(self):
        """Test gateway not found error."""
        error = GatewayNotFoundError("test-gateway")
        assert "test-gateway" in str(error)

    def test_gateway_connection_error(self):
        """Test gateway connection error."""
        error = GatewayConnectionError("http://localhost:4000", "Connection refused")
        assert "localhost:4000" in str(error)


class TestGatewayCapabilities:
    """Test gateway capability checking."""

    def test_capability_enum_values(self):
        """Test capability enum has expected values."""
        assert GatewayCapability.CHAT_COMPLETION is not None
        assert GatewayCapability.STREAMING is not None
        assert GatewayCapability.FUNCTION_CALLING is not None
        assert GatewayCapability.EMBEDDINGS is not None

    def test_adapter_has_capability(self):
        """Test checking adapter capability."""
        adapter = LiteLLMAdapter(
            name="test",
            base_url="http://localhost:4000",
            api_key="test-key",
        )
        assert adapter.has_capability(GatewayCapability.CHAT_COMPLETION)
        assert adapter.has_capability(GatewayCapability.STREAMING)


class TestModelRouting:
    """Test model routing through gateway abstraction."""

    def test_route_to_primary_gateway(self):
        """Test routing selects primary gateway."""
        registry = GatewayRegistry()
        adapter1 = LiteLLMAdapter(
            name="primary",
            base_url="http://localhost:4000",
            api_key="test-key",
        )
        adapter2 = OpenAIAdapter(
            name="fallback",
            api_key="test-key",
        )
        registry.register(adapter1)
        registry.register(adapter2)
        registry.set_default("primary")

        # Default routing should use primary
        gateway = registry.get_default()
        assert gateway.name == "primary"

    def test_route_by_model_pattern(self):
        """Test routing based on model pattern."""
        registry = GatewayRegistry()
        registry.register(
            LiteLLMAdapter(
                name="litellm",
                base_url="http://localhost:4000",
                api_key="test-key",
            )
        )
        registry.register(
            OpenAIAdapter(
                name="openai",
                api_key="test-key",
            )
        )

        # Configure routing rules
        routing_rules = {
            "gpt-*": ["litellm", "openai"],
            "claude-*": ["litellm"],
            "*": ["litellm"],
        }

        # Test pattern matching (implementation dependent)
        import fnmatch

        model = "gpt-4o-mini"
        for pattern, gateways in routing_rules.items():
            if fnmatch.fnmatch(model, pattern):
                assert "litellm" in gateways
                break


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
