"""Unit tests for the Rate Limits router (rate limit policies and events).

Tests the /api/v1/rate-limits and /api/v1/rate-limit-events endpoints.
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

_policy_row = _make_row({
    "id": "rl-1", "name": "Default", "description": "Default policy",
    "scope": "global", "scope_value": None, "rpm_limit": 100, "tpm_limit": 10000,
    "rpd_limit": None, "tpd_limit": None, "burst_multiplier": 1.5,
    "burst_window_seconds": 10, "priority": 0, "is_active": True,
    "created_at": "2024-01-01", "updated_at": None,
})

_event_row = _make_row({
    "id": "evt-1", "policy_id": "rl-1", "scope": "global", "scope_value": None,
    "limit_type": "rpm", "current_value": 110, "limit_value": 100,
    "action": "burst_allowed", "created_at": "2024-01-01",
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
# List Policies
# ============================================================================


class TestListPolicies:
    """Tests for GET /api/v1/rate-limits."""

    @pytest.mark.asyncio
    async def test_list_policies(self, client):
        conn = _make_async_conn(fetch_return=[_policy_row])
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/rate-limits")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "rl-1"
        assert data[0]["name"] == "Default"
        assert data[0]["scope"] == "global"
        assert data[0]["rpm_limit"] == 100

    @pytest.mark.asyncio
    async def test_list_policies_no_db(self, client):
        deps.db_pool = None

        async with client:
            resp = await client.get("/api/v1/rate-limits")

        assert resp.status_code == 503
        assert "Database not available" in resp.json()["detail"]


# ============================================================================
# Create Policy
# ============================================================================


class TestCreatePolicy:
    """Tests for POST /api/v1/rate-limits."""

    @pytest.mark.asyncio
    async def test_create_policy(self, client):
        conn = _make_async_conn(fetchrow_return=_policy_row)
        deps.db_pool = _make_pool(conn)
        deps.http_client = None  # No LiteLLM sync

        async with client:
            resp = await client.post("/api/v1/rate-limits", json={
                "name": "Default",
                "description": "Default policy",
                "scope": "global",
                "rpm_limit": 100,
                "tpm_limit": 10000,
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "rl-1"
        assert data["name"] == "Default"
        assert data["rpm_limit"] == 100


# ============================================================================
# Get Policy
# ============================================================================


class TestGetPolicy:
    """Tests for GET /api/v1/rate-limits/{id}."""

    @pytest.mark.asyncio
    async def test_get_policy(self, client):
        conn = _make_async_conn(fetchrow_return=_policy_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/rate-limits/rl-1")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "rl-1"
        assert data["scope"] == "global"

    @pytest.mark.asyncio
    async def test_get_policy_not_found(self, client):
        conn = _make_async_conn(fetchrow_return=None)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/rate-limits/nonexistent")

        assert resp.status_code == 404
        assert "Rate limit policy not found" in resp.json()["detail"]


# ============================================================================
# Update Policy
# ============================================================================


class TestUpdatePolicy:
    """Tests for PUT /api/v1/rate-limits/{id}."""

    @pytest.mark.asyncio
    async def test_update_policy(self, client):
        updated_row = _make_row({
            "id": "rl-1", "name": "Updated", "description": "Updated policy",
            "scope": "global", "scope_value": None, "rpm_limit": 200, "tpm_limit": 10000,
            "rpd_limit": None, "tpd_limit": None, "burst_multiplier": 1.5,
            "burst_window_seconds": 10, "priority": 0, "is_active": True,
            "created_at": "2024-01-01", "updated_at": "2024-06-01",
        })
        conn = _make_async_conn(fetchrow_return=updated_row)
        deps.db_pool = _make_pool(conn)
        deps.http_client = None  # No LiteLLM sync

        async with client:
            resp = await client.put("/api/v1/rate-limits/rl-1", json={
                "name": "Updated",
                "rpm_limit": 200,
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated"
        assert data["rpm_limit"] == 200

    @pytest.mark.asyncio
    async def test_update_policy_not_found(self, client):
        conn = _make_async_conn(fetchrow_return=None)
        deps.db_pool = _make_pool(conn)
        deps.http_client = None

        async with client:
            resp = await client.put("/api/v1/rate-limits/nonexistent", json={
                "name": "Updated",
            })

        assert resp.status_code == 404
        assert "Rate limit policy not found" in resp.json()["detail"]


# ============================================================================
# Delete Policy
# ============================================================================


class TestDeletePolicy:
    """Tests for DELETE /api/v1/rate-limits/{id}."""

    @pytest.mark.asyncio
    async def test_delete_policy(self, client):
        conn = _make_async_conn(fetchrow_return=_make_row({"scope": "global", "scope_value": None}))
        deps.db_pool = _make_pool(conn)
        deps.http_client = None

        async with client:
            resp = await client.delete("/api/v1/rate-limits/rl-1")

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_delete_policy_not_found(self, client):
        conn = _make_async_conn(fetchrow_return=None)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.delete("/api/v1/rate-limits/nonexistent")

        assert resp.status_code == 404
        assert "Rate limit policy not found" in resp.json()["detail"]


# ============================================================================
# Rate Limit Status
# ============================================================================


class TestRateLimitStatus:
    """Tests for GET /api/v1/rate-limits/status."""

    @pytest.mark.asyncio
    async def test_get_status(self, client):
        conn = _make_async_conn(fetch_return=[_policy_row])
        deps.db_pool = _make_pool(conn)
        deps.redis_client = None  # No Redis, counters return 0

        async with client:
            resp = await client.get("/api/v1/rate-limits/status")

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["scope"] == "global"
        assert data[0]["rpm_limit"] == 100


# ============================================================================
# Rate Limit Events
# ============================================================================


class TestRateLimitEvents:
    """Tests for GET /api/v1/rate-limit-events."""

    @pytest.mark.asyncio
    async def test_list_events(self, client):
        conn = _make_async_conn(fetch_return=[_event_row])
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/rate-limit-events")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "evt-1"
        assert data[0]["limit_type"] == "rpm"
        assert data[0]["action"] == "burst_allowed"

    @pytest.mark.asyncio
    async def test_list_events_no_db(self, client):
        deps.db_pool = None

        async with client:
            resp = await client.get("/api/v1/rate-limit-events")

        assert resp.status_code == 503
        assert "Database not available" in resp.json()["detail"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
