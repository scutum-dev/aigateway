"""Unit tests for the Agents router (A2A agent management).

Tests the /api/v1/agents endpoints.
"""

import importlib.util
import os
import sys
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

# ---------------------------------------------------------------------------
# Module loading
# ---------------------------------------------------------------------------

_service_dir = os.path.join(os.path.dirname(__file__), "../../src/admin-api")
sys.path.insert(0, _service_dir)

_otel_mock = MagicMock()
for mod_name in [
    "opentelemetry", "opentelemetry.trace", "opentelemetry.instrumentation",
    "opentelemetry.instrumentation.fastapi", "opentelemetry.exporter",
    "opentelemetry.exporter.otlp", "opentelemetry.exporter.otlp.proto",
    "opentelemetry.exporter.otlp.proto.grpc",
    "opentelemetry.exporter.otlp.proto.grpc.trace_exporter",
    "opentelemetry.sdk", "opentelemetry.sdk.trace",
    "opentelemetry.sdk.trace.export", "opentelemetry.sdk.resources",
]:
    sys.modules.setdefault(mod_name, _otel_mock)

_alembic_mock = MagicMock()
sys.modules.setdefault("alembic", _alembic_mock)
sys.modules.setdefault("alembic.config", _alembic_mock)
sys.modules.setdefault("alembic.command", _alembic_mock)

if "admin_api_main" not in sys.modules:
    _spec = importlib.util.spec_from_file_location("admin_api_main", os.path.join(_service_dir, "main.py"))
    _main_mod = importlib.util.module_from_spec(_spec)
    sys.modules["admin_api_main"] = _main_mod
    _spec.loader.exec_module(_main_mod)
else:
    _main_mod = sys.modules["admin_api_main"]

app = _main_mod.app

import deps  # noqa: E402
from auth import UserInfo, get_current_user, require_admin  # noqa: E402

# ---------------------------------------------------------------------------
# Auth override
# ---------------------------------------------------------------------------


def _fake_user():
    return UserInfo(user_id="test-admin", role="admin", is_admin=True)


app.dependency_overrides[get_current_user] = _fake_user
app.dependency_overrides[require_admin] = _fake_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_row(data: dict):
    row = MagicMock()
    row.__getitem__ = lambda self, key: data[key]
    row.__contains__ = lambda self, key: key in data
    row.get = lambda key, default=None: data.get(key, default)
    row.keys = lambda: data.keys()
    return row


def _make_async_conn(fetch_return=None, fetchrow_return=None, execute_return=None, fetchval_return=None):
    conn = AsyncMock()
    conn.fetch.return_value = fetch_return if fetch_return is not None else []
    conn.fetchrow.return_value = fetchrow_return
    conn.execute.return_value = execute_return or "DELETE 1"
    conn.fetchval.return_value = fetchval_return
    return conn


def _make_pool(conn):
    pool = MagicMock()
    ctx = AsyncMock()
    ctx.__aenter__.return_value = conn
    ctx.__aexit__.return_value = None
    pool.acquire.return_value = ctx
    return pool


# ---------------------------------------------------------------------------
# Mock rows
# ---------------------------------------------------------------------------

_agent_row = _make_row({
    "id": "agent-1", "name": "code-reviewer", "description": "Reviews code",
    "url": "http://localhost:9001", "skills": '["review","refactor"]',
    "is_active": True,
})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_deps():
    original_pool = deps.db_pool
    original_http = deps.http_client
    original_redis = deps.redis_client
    _main_mod._rate_limit_cache["value"] = 0
    _main_mod._rate_limit_cache["expires_at"] = 9999999999.0
    _main_mod._inmemory_requests.clear()
    yield
    deps.db_pool = original_pool
    deps.http_client = original_http
    deps.redis_client = original_redis


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# ============================================================================
# List Agents
# ============================================================================


class TestListAgents:
    """Tests for GET /api/v1/agents."""

    @pytest.mark.asyncio
    async def test_list_agents(self, client):
        conn = _make_async_conn(fetch_return=[_agent_row])
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/agents")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "agent-1"
        assert data[0]["name"] == "code-reviewer"
        assert data[0]["skills"] == ["review", "refactor"]

    @pytest.mark.asyncio
    async def test_list_agents_no_db(self, client):
        deps.db_pool = None

        async with client:
            resp = await client.get("/api/v1/agents")

        assert resp.status_code == 503
        assert "Database not available" in resp.json()["detail"]


# ============================================================================
# Create Agent
# ============================================================================


class TestCreateAgent:
    """Tests for POST /api/v1/agents."""

    @pytest.mark.asyncio
    async def test_create_agent(self, client):
        conn = _make_async_conn(fetchrow_return=_agent_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.post("/api/v1/agents", json={
                "name": "code-reviewer",
                "description": "Reviews code",
                "url": "http://localhost:9001",
                "skills": ["review", "refactor"],
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "agent-1"
        assert data["name"] == "code-reviewer"
        assert data["url"] == "http://localhost:9001"


# ============================================================================
# Get Agent
# ============================================================================


class TestGetAgent:
    """Tests for GET /api/v1/agents/{agent_id}."""

    @pytest.mark.asyncio
    async def test_get_agent(self, client):
        conn = _make_async_conn(fetchrow_return=_agent_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/agents/agent-1")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "agent-1"
        assert data["description"] == "Reviews code"

    @pytest.mark.asyncio
    async def test_get_agent_not_found(self, client):
        conn = _make_async_conn(fetchrow_return=None)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/agents/nonexistent")

        assert resp.status_code == 404
        assert "A2A agent not found" in resp.json()["detail"]


# ============================================================================
# Update Agent
# ============================================================================


class TestUpdateAgent:
    """Tests for PUT /api/v1/agents/{agent_id}."""

    @pytest.mark.asyncio
    async def test_update_agent(self, client):
        updated_row = _make_row({
            "id": "agent-1", "name": "code-reviewer-v2", "description": "Reviews code v2",
            "url": "http://localhost:9001", "skills": '["review","refactor","lint"]',
            "is_active": True,
        })
        conn = _make_async_conn(fetchrow_return=updated_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.put("/api/v1/agents/agent-1", json={
                "name": "code-reviewer-v2",
                "description": "Reviews code v2",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "code-reviewer-v2"

    @pytest.mark.asyncio
    async def test_update_agent_not_found(self, client):
        conn = _make_async_conn(fetchrow_return=None)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.put("/api/v1/agents/nonexistent", json={
                "name": "updated",
            })

        assert resp.status_code == 404
        assert "A2A agent not found" in resp.json()["detail"]


# ============================================================================
# Delete Agent
# ============================================================================


class TestDeleteAgent:
    """Tests for DELETE /api/v1/agents/{agent_id}."""

    @pytest.mark.asyncio
    async def test_delete_agent(self, client):
        conn = _make_async_conn(execute_return="DELETE 1")
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.delete("/api/v1/agents/agent-1")

        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    @pytest.mark.asyncio
    async def test_delete_agent_not_found(self, client):
        conn = _make_async_conn(execute_return="DELETE 0")
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.delete("/api/v1/agents/nonexistent")

        assert resp.status_code == 404
        assert "A2A agent not found" in resp.json()["detail"]


# ============================================================================
# Test Agent
# ============================================================================


class TestAgentConnectivity:
    """Tests for POST /api/v1/agents/{agent_id}/test."""

    @pytest.mark.asyncio
    async def test_test_agent(self, client):
        conn = _make_async_conn(fetchrow_return=_agent_row)
        deps.db_pool = _make_pool(conn)

        mock_response = MagicMock()
        mock_response.status_code = 200

        http_client = AsyncMock()
        http_client.get.return_value = mock_response
        deps.http_client = http_client

        async with client:
            resp = await client.post("/api/v1/agents/agent-1/test")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "Reachable" in data["message"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
