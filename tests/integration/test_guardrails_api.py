"""Integration tests for the Guardrails Admin API endpoints.

Tests CRUD, team assignment, events, and scan endpoints.
"""

import sys
import os
import importlib.util
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from uuid import uuid4

import pytest
import httpx

# Load the admin-api module
_service_dir = os.path.join(os.path.dirname(__file__), "../../src/admin-api")
sys.path.insert(0, _service_dir)

# We need to mock out heavy dependencies before importing
for mod_name in [
    "redis.asyncio", "jwt",
    "opentelemetry", "opentelemetry.trace",
    "opentelemetry.instrumentation.fastapi",
    "opentelemetry.exporter.otlp.proto.grpc.trace_exporter",
    "opentelemetry.sdk.trace", "opentelemetry.sdk.trace.export",
    "opentelemetry.sdk.resources",
    "alembic", "alembic.config", "alembic.command",
    "passlib", "passlib.context",
]:
    sys.modules.setdefault(mod_name, MagicMock())

import deps
from auth import get_current_user, require_admin
from routers.guardrails import router, GuardrailConfig, GuardrailEvent

from fastapi import FastAPI
from fastapi.testclient import TestClient

# Fake user for auth overrides
_fake_user = MagicMock(user_id="admin", role="admin")

# Build a minimal app with the guardrails router
test_app = FastAPI()
test_app.dependency_overrides[get_current_user] = lambda: _fake_user
test_app.dependency_overrides[require_admin] = lambda: _fake_user
test_app.include_router(router, prefix="/api/v1")


SAMPLE_CONFIG_ROW = {
    "id": uuid4(),
    "name": "test-profile",
    "description": "Test guardrail",
    "enable_prompt_injection": True,
    "prompt_injection_threshold": 0.90,
    "enable_pii_detection": True,
    "pii_action": "anonymize",
    "pii_entities": ["PERSON", "EMAIL_ADDRESS"],
    "enable_toxicity": True,
    "toxicity_threshold": 0.70,
    "banned_topics": [],
    "enable_secrets_detection": True,
    "enable_invisible_text": True,
    "enable_malicious_urls": True,
    "enable_sensitive_output": True,
    "mode": "block",
    "on_fail": "block",
    "is_active": True,
    "created_at": datetime.now(timezone.utc),
    "updated_at": datetime.now(timezone.utc),
}

SAMPLE_EVENT_ROW = {
    "id": uuid4(),
    "event_type": "input_blocked",
    "scanner_name": "PromptInjection",
    "user_id": "user-1",
    "team_id": "team-1",
    "model": "gpt-4o",
    "risk_score": 0.95,
    "action_taken": "blocked",
    "details": '{"direction": "input"}',
    "created_at": datetime.now(timezone.utc),
}


@pytest.fixture
def mock_pool():
    """Mock asyncpg pool with connection context manager."""
    conn = AsyncMock()
    pool = MagicMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = ctx
    original = deps.db_pool
    deps.db_pool = pool
    yield pool, conn
    deps.db_pool = original


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=test_app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# ============================================================================
# List guardrails
# ============================================================================


class TestListGuardrails:
    @pytest.mark.asyncio
    async def test_list_empty(self, client, mock_pool):
        _, conn = mock_pool
        conn.fetch.return_value = []
        resp = await client.get("/api/v1/guardrails")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_list_with_data(self, client, mock_pool):
        _, conn = mock_pool
        conn.fetch.return_value = [SAMPLE_CONFIG_ROW]
        resp = await client.get("/api/v1/guardrails")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "test-profile"

    @pytest.mark.asyncio
    async def test_list_no_db(self, client):
        original = deps.db_pool
        deps.db_pool = None
        resp = await client.get("/api/v1/guardrails")
        assert resp.status_code == 503
        deps.db_pool = original


# ============================================================================
# Create guardrail
# ============================================================================


class TestCreateGuardrail:
    @pytest.mark.asyncio
    async def test_create_success(self, client, mock_pool):
        _, conn = mock_pool
        conn.fetchrow.return_value = SAMPLE_CONFIG_ROW
        resp = await client.post("/api/v1/guardrails", json={
            "name": "test-profile",
            "description": "Test guardrail",
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "test-profile"


# ============================================================================
# Get guardrail
# ============================================================================


class TestGetGuardrail:
    @pytest.mark.asyncio
    async def test_get_found(self, client, mock_pool):
        _, conn = mock_pool
        conn.fetchrow.return_value = SAMPLE_CONFIG_ROW
        resp = await client.get(f"/api/v1/guardrails/{SAMPLE_CONFIG_ROW['id']}")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_not_found(self, client, mock_pool):
        _, conn = mock_pool
        conn.fetchrow.return_value = None
        resp = await client.get(f"/api/v1/guardrails/{uuid4()}")
        assert resp.status_code == 404


# ============================================================================
# Update guardrail
# ============================================================================


class TestUpdateGuardrail:
    @pytest.mark.asyncio
    async def test_update_success(self, client, mock_pool):
        _, conn = mock_pool
        conn.fetchrow.return_value = SAMPLE_CONFIG_ROW
        resp = await client.put(f"/api/v1/guardrails/{SAMPLE_CONFIG_ROW['id']}", json={
            "enable_toxicity": False,
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_update_empty_body(self, client, mock_pool):
        resp = await client.put(f"/api/v1/guardrails/{uuid4()}", json={})
        assert resp.status_code == 400


# ============================================================================
# Delete guardrail
# ============================================================================


class TestDeleteGuardrail:
    @pytest.mark.asyncio
    async def test_delete_success(self, client, mock_pool):
        _, conn = mock_pool
        conn.execute.return_value = "DELETE 1"
        resp = await client.delete(f"/api/v1/guardrails/{SAMPLE_CONFIG_ROW['id']}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    @pytest.mark.asyncio
    async def test_delete_not_found(self, client, mock_pool):
        _, conn = mock_pool
        conn.execute.return_value = "DELETE 0"
        resp = await client.delete(f"/api/v1/guardrails/{uuid4()}")
        assert resp.status_code == 404


# ============================================================================
# Team assignment
# ============================================================================


class TestTeamAssignment:
    @pytest.mark.asyncio
    async def test_assign(self, client, mock_pool):
        _, conn = mock_pool
        resp = await client.post(f"/api/v1/guardrails/{SAMPLE_CONFIG_ROW['id']}/assign/{uuid4()}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "assigned"

    @pytest.mark.asyncio
    async def test_unassign_success(self, client, mock_pool):
        _, conn = mock_pool
        conn.execute.return_value = "DELETE 1"
        resp = await client.delete(f"/api/v1/guardrails/{SAMPLE_CONFIG_ROW['id']}/assign/{uuid4()}")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_unassign_not_found(self, client, mock_pool):
        _, conn = mock_pool
        conn.execute.return_value = "DELETE 0"
        resp = await client.delete(f"/api/v1/guardrails/{SAMPLE_CONFIG_ROW['id']}/assign/{uuid4()}")
        assert resp.status_code == 404


# ============================================================================
# Events
# ============================================================================


class TestGuardrailEvents:
    @pytest.mark.asyncio
    async def test_list_events_empty(self, client, mock_pool):
        _, conn = mock_pool
        conn.fetch.return_value = []
        resp = await client.get("/api/v1/guardrail-events")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_list_events_with_data(self, client, mock_pool):
        _, conn = mock_pool
        conn.fetch.return_value = [SAMPLE_EVENT_ROW]
        resp = await client.get("/api/v1/guardrail-events")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["event_type"] == "input_blocked"

    @pytest.mark.asyncio
    async def test_list_events_with_filters(self, client, mock_pool):
        _, conn = mock_pool
        conn.fetch.return_value = []
        resp = await client.get("/api/v1/guardrail-events", params={
            "team_id": "team-1",
            "event_type": "pii_detected",
        })
        assert resp.status_code == 200


# ============================================================================
# Scan endpoint
# ============================================================================


class TestScanEndpoint:
    @pytest.mark.asyncio
    async def test_scan_llm_guard_not_installed(self, client, mock_pool):
        """Should return 501 when LLM Guard is not available."""
        resp = await client.post("/api/v1/guardrails/scan", json={
            "text": "test input",
            "direction": "input",
        })
        # In test environment, llm_guard won't be installed → 501
        assert resp.status_code == 501
