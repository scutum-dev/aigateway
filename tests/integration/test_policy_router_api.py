"""Integration tests for the Policy Router API.

Tests HTTP endpoints, ServiceAuthMiddleware, Cedar policy evaluation,
and model routing logic.
"""

import sys
import os
import importlib.util
from unittest.mock import AsyncMock, MagicMock

import pytest
import httpx

# Load the policy-router module
_service_dir = os.path.join(os.path.dirname(__file__), "../../src/policy-router")
_service_path = os.path.join(_service_dir, "main.py")
sys.path.insert(0, _service_dir)
_spec = importlib.util.spec_from_file_location("policy_router_integ", _service_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["policy_router_integ"] = _mod
_spec.loader.exec_module(_mod)

app = _mod.app

from routing_strategy import RoutingStrategy

SERVICE_KEY = "test-integration-key"


@pytest.fixture(autouse=True)
def _reset_state():
    """Reset module state between tests."""
    original_key = _mod.INTERNAL_SERVICE_KEY
    original_db = _mod.db_pool
    original_http = _mod.http_client
    original_redis = _mod.redis_client
    original_cedar = _mod.cedar_engine
    original_metrics = _mod.metrics_collector
    original_routing = _mod.routing_strategy
    yield
    _mod.INTERNAL_SERVICE_KEY = original_key
    _mod.db_pool = original_db
    _mod.http_client = original_http
    _mod.redis_client = original_redis
    _mod.cedar_engine = original_cedar
    _mod.metrics_collector = original_metrics
    _mod.routing_strategy = original_routing


@pytest.fixture
def client():
    """ASGI test client (dev mode, no auth)."""
    _mod.INTERNAL_SERVICE_KEY = ""
    _mod.db_pool = None
    _mod.http_client = AsyncMock()
    _mod.redis_client = None
    _mod.cedar_engine = None
    _mod.metrics_collector = None
    _mod.routing_strategy = RoutingStrategy()
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def authed_client():
    """ASGI test client with auth required."""
    _mod.INTERNAL_SERVICE_KEY = SERVICE_KEY
    _mod.db_pool = None
    _mod.http_client = AsyncMock()
    _mod.redis_client = None
    _mod.cedar_engine = None
    _mod.metrics_collector = None
    _mod.routing_strategy = RoutingStrategy()
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
    async def test_models_requires_auth(self, authed_client):
        """Models endpoint should require service key."""
        resp = await authed_client.get("/models")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_models_with_correct_key(self, authed_client):
        """Models endpoint should work with correct key."""
        resp = await authed_client.get(
            "/models",
            headers={"X-Service-Key": SERVICE_KEY}
        )
        assert resp.status_code != 401

    @pytest.mark.asyncio
    async def test_dev_mode_no_auth_required(self, client):
        """Dev mode (empty key) should allow all requests."""
        resp = await client.get("/models")
        assert resp.status_code != 401


# ============================================================================
# /health
# ============================================================================


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health(self, client):
        """Health endpoint should return healthy status."""
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


# ============================================================================
# POST /route
# ============================================================================


class TestRouteEndpoint:
    @pytest.mark.asyncio
    async def test_route_returns_decision(self, client):
        """Route should return a routing decision with default models."""
        resp = await client.post("/route", json={
            "user_id": "user-1",
            "priority": "normal",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "selected_model" in data
        assert "fallback_models" in data
        assert "decision_reason" in data

    @pytest.mark.asyncio
    async def test_route_empty_request(self, client):
        """Route with empty request should return a model from defaults."""
        resp = await client.post("/route", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["selected_model"] in [
            "gpt-4o", "gpt-4o-mini", "claude-3-5-sonnet",
            "claude-3-haiku", "grok-3", "llama-3.1-70b",
        ]

    @pytest.mark.asyncio
    async def test_route_with_budget_constraint(self, client):
        """Route with tight budget should prefer cheaper models."""
        resp = await client.post("/route", json={
            "user_id": "user-1",
            "budget_remaining": 1.0,
            "priority": "normal",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["selected_model"] is not None
        assert isinstance(data["fallback_models"], list)


# ============================================================================
# POST /evaluate
# ============================================================================


class TestEvaluateEndpoint:
    @pytest.mark.asyncio
    async def test_evaluate_without_cedar_engine(self, client):
        """Evaluate should return 503 when cedar engine is unavailable."""
        _mod.cedar_engine = None
        resp = await client.post("/evaluate", json={
            "principal": "user::test-user",
            "action": "use",
            "resource": "model::gpt-4o",
            "context": {},
        })
        assert resp.status_code == 503


# ============================================================================
# GET /models
# ============================================================================


class TestModelsEndpoint:
    @pytest.mark.asyncio
    async def test_list_models(self, client):
        """Models endpoint should return default model list."""
        resp = await client.get("/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        model_ids = [m["model_id"] for m in data["models"]]
        assert "gpt-4o" in model_ids
        assert "claude-3-5-sonnet" in model_ids
        assert len(data["models"]) == len(_mod.DEFAULT_MODELS)


# ============================================================================
# POST /policies/reload
# ============================================================================


class TestPoliciesReloadEndpoint:
    @pytest.mark.asyncio
    async def test_reload_without_cedar_engine(self, client):
        """Policies reload should return 503 when cedar engine is unavailable."""
        _mod.cedar_engine = None
        resp = await client.post("/policies/reload")
        assert resp.status_code == 503


# ============================================================================
# GET /decisions
# ============================================================================


class TestDecisionsEndpoint:
    @pytest.mark.asyncio
    async def test_decisions_without_db(self, client):
        """Decisions should return empty list when database is unavailable."""
        _mod.db_pool = None
        resp = await client.get("/decisions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["decisions"] == []
        assert "message" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
