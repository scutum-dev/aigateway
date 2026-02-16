"""Integration tests for the Budget Webhook API.

Tests HTTP endpoints, ServiceAuthMiddleware, and pre/post request logic.
"""

import sys
import os
import importlib.util
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal

import pytest
import httpx

# Load the budget-webhook module
_service_dir = os.path.join(os.path.dirname(__file__), "../../src/budget-webhook")
_service_path = os.path.join(_service_dir, "main.py")
sys.path.insert(0, _service_dir)
_spec = importlib.util.spec_from_file_location("budget_webhook_integ", _service_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["budget_webhook_integ"] = _mod
_spec.loader.exec_module(_mod)

app = _mod.app

SERVICE_KEY = "test-integration-key"


@pytest.fixture(autouse=True)
def _reset_state():
    """Reset module state between tests."""
    original_key = _mod.INTERNAL_SERVICE_KEY
    original_db = _mod.db_pool
    original_http = _mod.http_client
    yield
    _mod.INTERNAL_SERVICE_KEY = original_key
    _mod.db_pool = original_db
    _mod.http_client = original_http


@pytest.fixture
def client():
    """ASGI test client (dev mode, no auth)."""
    _mod.INTERNAL_SERVICE_KEY = ""
    _mod.db_pool = None
    _mod.http_client = AsyncMock()
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def authed_client():
    """ASGI test client with auth required."""
    _mod.INTERNAL_SERVICE_KEY = SERVICE_KEY
    _mod.db_pool = None
    _mod.http_client = AsyncMock()
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

    @pytest.mark.asyncio
    async def test_webhook_pre_request_exempt(self, authed_client):
        """LiteLLM webhook endpoints should bypass auth."""
        # Mock dependencies so the endpoint logic works
        _mod.http_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        _mod.http_client.get.return_value = mock_resp
        _mod.http_client.post.return_value = MagicMock(status_code=500)

        resp = await authed_client.post("/webhook/pre-request", json={
            "data": {"model": "gpt-4o", "api_key": "sk-test"}
        })
        # Should not be 401 — endpoint is exempt from service auth
        assert resp.status_code != 401

    @pytest.mark.asyncio
    async def test_webhook_post_request_exempt(self, authed_client):
        """Post-request webhook should bypass auth."""
        resp = await authed_client.post("/webhook/post-request", json={
            "data": {"model": "gpt-4o", "cost": 0.001}
        })
        assert resp.status_code != 401

    @pytest.mark.asyncio
    async def test_alerts_requires_auth(self, authed_client):
        """Alerts endpoint should require service key."""
        resp = await authed_client.get("/alerts")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_alerts_with_correct_key(self, authed_client):
        """Alerts endpoint should work with correct key."""
        resp = await authed_client.get(
            "/alerts",
            headers={"X-Service-Key": SERVICE_KEY}
        )
        # Should not be 401 (might be 200 or 503 depending on DB)
        assert resp.status_code != 401


# ============================================================================
# /health
# ============================================================================


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


# ============================================================================
# /webhook/pre-request
# ============================================================================


class TestPreRequestWebhook:
    @pytest.mark.asyncio
    async def test_allow_when_no_budget_info(self, client):
        """Should allow when budget info is unavailable."""
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        _mod.http_client.get.return_value = mock_resp

        resp = await client.post("/webhook/pre-request", json={
            "data": {"model": "gpt-4o", "api_key": "sk-test", "messages": []}
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["allow"] is True

    @pytest.mark.asyncio
    async def test_allow_when_no_budget_limit(self, client):
        """Should allow when no budget limit is set."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"max_budget": None, "spend": 10.0}
        _mod.http_client.get.return_value = mock_resp

        resp = await client.post("/webhook/pre-request", json={
            "data": {"model": "gpt-4o", "api_key": "sk-test", "messages": []}
        })
        assert resp.status_code == 200
        assert resp.json()["allow"] is True

    @pytest.mark.asyncio
    async def test_block_at_hard_limit(self, client):
        """Should block when budget is exceeded (hard limit)."""
        mock_budget = MagicMock()
        mock_budget.status_code = 200
        mock_budget.json.return_value = {"max_budget": 100.0, "spend": 100.0}
        _mod.http_client.get.return_value = mock_budget

        mock_cost = MagicMock()
        mock_cost.status_code = 200
        mock_cost.json.return_value = {"total_estimated_cost_usd": 0.01}
        _mod.http_client.post.return_value = mock_cost

        with patch.object(_mod, "send_notification", new_callable=AsyncMock):
            resp = await client.post("/webhook/pre-request", json={
                "data": {"model": "gpt-4o", "api_key": "sk-test", "messages": []}
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["allow"] is False
        assert "exceeded" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_warn_at_soft_limit(self, client):
        """Should allow with warning at soft limit."""
        mock_budget = MagicMock()
        mock_budget.status_code = 200
        mock_budget.json.return_value = {"max_budget": 100.0, "spend": 85.0}
        _mod.http_client.get.return_value = mock_budget

        mock_cost = MagicMock()
        mock_cost.status_code = 200
        mock_cost.json.return_value = {"total_estimated_cost_usd": 0.001}
        _mod.http_client.post.return_value = mock_cost

        with patch.object(_mod, "send_notification", new_callable=AsyncMock):
            resp = await client.post("/webhook/pre-request", json={
                "data": {"model": "gpt-4o", "api_key": "sk-test", "messages": []}
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["allow"] is True
        assert "warning" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_allow_within_budget(self, client):
        """Should allow when well within budget."""
        mock_budget = MagicMock()
        mock_budget.status_code = 200
        mock_budget.json.return_value = {"max_budget": 100.0, "spend": 10.0}
        _mod.http_client.get.return_value = mock_budget

        mock_cost = MagicMock()
        mock_cost.status_code = 200
        mock_cost.json.return_value = {"total_estimated_cost_usd": 0.001}
        _mod.http_client.post.return_value = mock_cost

        resp = await client.post("/webhook/pre-request", json={
            "data": {"model": "gpt-4o", "api_key": "sk-test", "messages": []}
        })
        assert resp.status_code == 200
        assert resp.json()["allow"] is True


# ============================================================================
# /webhook/post-request
# ============================================================================


class TestPostRequestWebhook:
    @pytest.mark.asyncio
    async def test_record_without_db(self, client):
        """Should succeed even without database."""
        _mod.db_pool = None
        resp = await client.post("/webhook/post-request", json={
            "data": {
                "model": "gpt-4o",
                "user": "user-1",
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
                "cost": 0.005,
            }
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "recorded"

    @pytest.mark.asyncio
    async def test_record_with_db(self, client):
        """Should record to database when available."""
        conn = AsyncMock()
        pool = MagicMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=conn)
        ctx.__aexit__ = AsyncMock(return_value=None)
        pool.acquire.return_value = ctx
        _mod.db_pool = pool

        resp = await client.post("/webhook/post-request", json={
            "data": {
                "model": "gpt-4o",
                "user": "user-1",
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
                "cost": 0.005,
            }
        })
        assert resp.status_code == 200
        conn.execute.assert_called_once()


# ============================================================================
# /alerts
# ============================================================================


class TestAlertsEndpoint:
    @pytest.mark.asyncio
    async def test_alerts_no_db(self, client):
        """Should return empty alerts when no database."""
        _mod.db_pool = None
        resp = await client.get("/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["alerts"] == []
