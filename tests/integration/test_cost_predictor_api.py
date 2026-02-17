"""Integration tests for the Cost Predictor API.

Tests HTTP endpoints and ServiceAuthMiddleware via ASGI test client.
"""

import importlib.util
import os
from unittest.mock import AsyncMock

import httpx
import pytest

# Load the cost-predictor module
_service_path = os.path.join(os.path.dirname(__file__), "../../src/cost-predictor/main.py")
_spec = importlib.util.spec_from_file_location("cost_predictor_integ", _service_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

app = _mod.app

SERVICE_KEY = "test-integration-key"


@pytest.fixture(autouse=True)
def _clear_service_key():
    """Reset INTERNAL_SERVICE_KEY for each test."""
    original = _mod.INTERNAL_SERVICE_KEY
    yield
    _mod.INTERNAL_SERVICE_KEY = original


@pytest.fixture
def client():
    """ASGI test client with no auth required (dev mode)."""
    _mod.INTERNAL_SERVICE_KEY = ""
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def authed_client():
    """ASGI test client with auth required."""
    _mod.INTERNAL_SERVICE_KEY = SERVICE_KEY
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# ============================================================================
# ServiceAuthMiddleware
# ============================================================================


class TestServiceAuthMiddleware:
    @pytest.mark.asyncio
    async def test_health_exempt(self, authed_client):
        """Health endpoint should bypass auth."""
        resp = await authed_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_reject_without_key(self, authed_client):
        """Protected endpoint should return 401 without service key."""
        resp = await authed_client.get("/pricing")
        assert resp.status_code == 401
        assert "Unauthorized" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_reject_wrong_key(self, authed_client):
        """Protected endpoint should return 401 with wrong key."""
        resp = await authed_client.get("/pricing", headers={"X-Service-Key": "wrong-key"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_accept_correct_key(self, authed_client):
        """Protected endpoint should return 200 with correct key."""
        resp = await authed_client.get("/pricing", headers={"X-Service-Key": SERVICE_KEY})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_dev_mode_no_auth(self, client):
        """Dev mode (empty key) should allow all requests."""
        resp = await client.get("/pricing")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_options_exempt(self, authed_client):
        """OPTIONS requests should bypass auth (CORS preflight)."""
        resp = await authed_client.options("/pricing")
        assert resp.status_code != 401


# ============================================================================
# /health
# ============================================================================


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "healthy"}


# ============================================================================
# /predict
# ============================================================================


class TestPredictEndpoint:
    @pytest.mark.asyncio
    async def test_predict_messages(self, client):
        """Should return cost prediction for messages."""
        resp = await client.post(
            "/predict",
            json={
                "model": "gpt-4o",
                "messages": [
                    {"role": "system", "content": "You are helpful."},
                    {"role": "user", "content": "Hello, how are you?"},
                ],
                "max_tokens": 500,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["model"] == "gpt-4o"
        assert data["input_tokens"] > 0
        assert data["estimated_output_tokens"] > 0
        assert data["total_estimated_cost_usd"] > 0
        assert data["within_budget"] is True

    @pytest.mark.asyncio
    async def test_predict_prompt(self, client):
        """Should accept a plain text prompt."""
        resp = await client.post(
            "/predict",
            json={
                "model": "gpt-4o",
                "prompt": "What is the meaning of life?",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["input_tokens"] > 0

    @pytest.mark.asyncio
    async def test_predict_no_input(self, client):
        """Should return 400 when no messages or prompt."""
        resp = await client.post(
            "/predict",
            json={
                "model": "gpt-4o",
            },
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_predict_unknown_model(self, client):
        """Should use default pricing for unknown models."""
        resp = await client.post(
            "/predict",
            json={
                "model": "totally-unknown-model",
                "prompt": "Hello",
                "max_tokens": 100,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["total_estimated_cost_usd"] > 0


# ============================================================================
# /pricing
# ============================================================================


class TestPricingEndpoint:
    @pytest.mark.asyncio
    async def test_get_pricing(self, client):
        """Should return pricing for all models."""
        resp = await client.get("/pricing")
        assert resp.status_code == 200
        data = resp.json()
        assert "gpt-4o" in data
        assert "input_cost_per_million" in data["gpt-4o"]
        assert "output_cost_per_million" in data["gpt-4o"]

    @pytest.mark.asyncio
    async def test_update_pricing(self, client):
        """Should update pricing for a model."""
        resp = await client.post(
            "/pricing/update", params={"model": "test-model", "input_cost": 1.5, "output_cost": 3.0}
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"

        # Verify it's reflected in GET
        resp = await client.get("/pricing")
        assert "test-model" in resp.json()


# ============================================================================
# /budget/check
# ============================================================================


class TestBudgetCheckEndpoint:
    @pytest.mark.asyncio
    async def test_budget_check_no_litellm(self, client):
        """Should handle missing LiteLLM gracefully."""
        _mod.http_client = AsyncMock()
        _mod.http_client.get.side_effect = httpx.ConnectError("Connection refused")

        resp = await client.post(
            "/budget/check",
            json={
                "api_key": "sk-test",
                "estimated_cost": 0.01,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["allowed"] is True  # fails open
