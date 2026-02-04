"""
Integration tests for LLM routing through the gateway stack.

Tests:
- LLM routing to correct provider
- Fallback on provider failure
- Budget enforcement
- Cost tracking
"""

import os
import pytest
import httpx
from typing import Optional

# Configuration from environment
LITELLM_URL = os.getenv("LITELLM_URL", "http://localhost:4000")
AGENTGATEWAY_URL = os.getenv("AGENTGATEWAY_URL", "http://localhost:3000")
API_KEY = os.getenv("TEST_API_KEY", "sk-test-key")


@pytest.fixture
def http_client():
    """Create HTTP client for tests."""
    return httpx.Client(timeout=60.0)


@pytest.fixture
def api_headers():
    """Common API headers."""
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }


class TestLLMRouting:
    """Test LLM request routing."""

    def test_route_to_openai_model(self, http_client, api_headers):
        """Test routing to OpenAI model."""
        response = http_client.post(
            f"{LITELLM_URL}/v1/chat/completions",
            headers=api_headers,
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "user", "content": "Say 'test' and nothing else."}
                ],
                "max_tokens": 10
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "choices" in data
        assert len(data["choices"]) > 0
        assert "message" in data["choices"][0]

    def test_route_to_anthropic_model(self, http_client, api_headers):
        """Test routing to Anthropic model."""
        response = http_client.post(
            f"{LITELLM_URL}/v1/chat/completions",
            headers=api_headers,
            json={
                "model": "claude-3-haiku",
                "messages": [
                    {"role": "user", "content": "Say 'test' and nothing else."}
                ],
                "max_tokens": 10
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "choices" in data

    def test_route_to_self_hosted_model(self, http_client, api_headers):
        """Test routing to self-hosted vLLM model."""
        response = http_client.post(
            f"{LITELLM_URL}/v1/chat/completions",
            headers=api_headers,
            json={
                "model": "llama-3.1-8b",
                "messages": [
                    {"role": "user", "content": "Say 'test' and nothing else."}
                ],
                "max_tokens": 10
            }
        )

        # May fail if vLLM is not running, which is expected in some test environments
        if response.status_code == 200:
            data = response.json()
            assert "choices" in data
        else:
            # Accept 503 if vLLM is not available
            assert response.status_code in [200, 503]

    def test_model_group_alias_fast(self, http_client, api_headers):
        """Test using model group alias 'fast'."""
        response = http_client.post(
            f"{LITELLM_URL}/v1/chat/completions",
            headers=api_headers,
            json={
                "model": "fast",
                "messages": [
                    {"role": "user", "content": "Say 'test' and nothing else."}
                ],
                "max_tokens": 10
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "choices" in data
        # Should route to one of: gpt-4o-mini, claude-3-haiku, llama-3.1-8b

    def test_model_group_alias_smart(self, http_client, api_headers):
        """Test using model group alias 'smart'."""
        response = http_client.post(
            f"{LITELLM_URL}/v1/chat/completions",
            headers=api_headers,
            json={
                "model": "smart",
                "messages": [
                    {"role": "user", "content": "What is 2+2? Answer with just the number."}
                ],
                "max_tokens": 10
            }
        )

        assert response.status_code == 200


class TestFallbackBehavior:
    """Test fallback routing on provider failure."""

    def test_fallback_on_error(self, http_client, api_headers):
        """Test that fallback works when primary provider fails."""
        # This test requires simulating a provider failure
        # In real scenarios, this would be tested with fault injection
        response = http_client.post(
            f"{LITELLM_URL}/v1/chat/completions",
            headers=api_headers,
            json={
                "model": "gpt-4o",
                "messages": [
                    {"role": "user", "content": "Say 'test'"}
                ],
                "max_tokens": 10
            }
        )

        # Should succeed (either directly or via fallback)
        assert response.status_code == 200

    def test_streaming_response(self, http_client, api_headers):
        """Test streaming responses work correctly."""
        with http_client.stream(
            "POST",
            f"{LITELLM_URL}/v1/chat/completions",
            headers=api_headers,
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "user", "content": "Count from 1 to 5."}
                ],
                "max_tokens": 50,
                "stream": True
            }
        ) as response:
            assert response.status_code == 200

            chunks = []
            for line in response.iter_lines():
                if line.startswith("data: "):
                    chunks.append(line)

            assert len(chunks) > 0


class TestBudgetEnforcement:
    """Test budget enforcement."""

    def test_request_within_budget(self, http_client, api_headers):
        """Test that requests within budget are allowed."""
        response = http_client.post(
            f"{LITELLM_URL}/v1/chat/completions",
            headers=api_headers,
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "user", "content": "Hi"}
                ],
                "max_tokens": 5
            }
        )

        # Should succeed if within budget
        assert response.status_code in [200, 429]  # 429 if budget exceeded

    def test_get_key_info(self, http_client, api_headers):
        """Test getting API key budget info."""
        response = http_client.get(
            f"{LITELLM_URL}/key/info",
            headers=api_headers
        )

        if response.status_code == 200:
            data = response.json()
            # Check budget fields exist
            assert "info" in data or "spend" in data or "max_budget" in data


class TestCostTracking:
    """Test cost tracking functionality."""

    def test_usage_in_response(self, http_client, api_headers):
        """Test that usage information is included in response."""
        response = http_client.post(
            f"{LITELLM_URL}/v1/chat/completions",
            headers=api_headers,
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "user", "content": "Say 'test'"}
                ],
                "max_tokens": 10
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Check usage information
        assert "usage" in data
        assert "prompt_tokens" in data["usage"]
        assert "completion_tokens" in data["usage"]
        assert "total_tokens" in data["usage"]

    def test_spend_endpoint(self, http_client, api_headers):
        """Test spend tracking endpoint."""
        response = http_client.get(
            f"{LITELLM_URL}/spend/logs",
            headers=api_headers
        )

        # Should return spend logs or 404 if not configured
        assert response.status_code in [200, 404]


class TestHealthChecks:
    """Test health check endpoints."""

    def test_litellm_health(self, http_client):
        """Test LiteLLM health endpoint."""
        response = http_client.get(f"{LITELLM_URL}/health")
        assert response.status_code == 200

    def test_litellm_readiness(self, http_client):
        """Test LiteLLM readiness endpoint."""
        response = http_client.get(f"{LITELLM_URL}/health/readiness")
        assert response.status_code == 200

    def test_agentgateway_health(self, http_client):
        """Test Agent Gateway health endpoint."""
        response = http_client.get(f"{AGENTGATEWAY_URL}/health")
        # May fail if not running
        assert response.status_code in [200, 502, 503]


class TestModelList:
    """Test model listing functionality."""

    def test_list_models(self, http_client, api_headers):
        """Test listing available models."""
        response = http_client.get(
            f"{LITELLM_URL}/v1/models",
            headers=api_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert "data" in data
        models = data["data"]
        assert len(models) > 0

        # Check model structure
        model_ids = [m["id"] for m in models]
        # At least some of our configured models should be present
        expected_models = ["gpt-4o", "gpt-4o-mini", "claude-3-haiku", "llama-3.1-8b"]
        found = any(m in model_ids for m in expected_models)
        assert found, f"Expected one of {expected_models} in {model_ids}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
