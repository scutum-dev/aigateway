"""Unit tests for the Model Access router (tiers and access requests).

Tests the /api/v1/model-access/tiers and /api/v1/model-access/requests endpoints.
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
    "opentelemetry",
    "opentelemetry.trace",
    "opentelemetry.instrumentation",
    "opentelemetry.instrumentation.fastapi",
    "opentelemetry.exporter",
    "opentelemetry.exporter.otlp",
    "opentelemetry.exporter.otlp.proto",
    "opentelemetry.exporter.otlp.proto.grpc",
    "opentelemetry.exporter.otlp.proto.grpc.trace_exporter",
    "opentelemetry.sdk",
    "opentelemetry.sdk.trace",
    "opentelemetry.sdk.trace.export",
    "opentelemetry.sdk.resources",
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

_tier_row = _make_row(
    {
        "id": "tier-1",
        "name": "Standard",
        "description": "Standard access",
        "requires_approval": False,
        "requires_justification": False,
        "max_grant_duration_days": None,
        "models": ["gpt-4o-mini", "gpt-4o"],
        "created_at": "2024-01-01",
    }
)

_request_row = _make_row(
    {
        "id": "req-1",
        "user_id": "test-admin",
        "team_id": None,
        "model_pattern": "claude-*",
        "tier_id": "tier-1",
        "justification": "Need for project",
        "status": "pending",
        "reviewer": None,
        "review_comment": None,
        "granted_at": None,
        "expires_at": None,
        "created_at": "2024-01-01",
    }
)


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
# List Tiers
# ============================================================================


class TestListTiers:
    """Tests for GET /api/v1/model-access/tiers."""

    @pytest.mark.asyncio
    async def test_list_tiers(self, client):
        conn = _make_async_conn(fetch_return=[_tier_row])
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/model-access/tiers")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "tier-1"
        assert data[0]["name"] == "Standard"
        assert data[0]["models"] == ["gpt-4o-mini", "gpt-4o"]

    @pytest.mark.asyncio
    async def test_list_tiers_no_db(self, client):
        deps.db_pool = None

        async with client:
            resp = await client.get("/api/v1/model-access/tiers")

        assert resp.status_code == 503
        assert "Database not available" in resp.json()["detail"]


# ============================================================================
# Create Tier
# ============================================================================


class TestCreateTier:
    """Tests for POST /api/v1/model-access/tiers."""

    @pytest.mark.asyncio
    async def test_create_tier(self, client):
        conn = _make_async_conn(fetchrow_return=_tier_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.post(
                "/api/v1/model-access/tiers",
                json={
                    "name": "Standard",
                    "description": "Standard access",
                    "requires_approval": False,
                    "models": ["gpt-4o-mini", "gpt-4o"],
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "tier-1"
        assert data["name"] == "Standard"


# ============================================================================
# Get Tier
# ============================================================================


class TestGetTier:
    """Tests for GET /api/v1/model-access/tiers/{id} (via PUT since no dedicated GET)."""

    @pytest.mark.asyncio
    async def test_get_tier(self, client):
        """Update tier with no changes to verify it returns existing data."""
        conn = _make_async_conn(fetchrow_return=_tier_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.put(
                "/api/v1/model-access/tiers/tier-1",
                json={
                    "name": "Standard",
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "tier-1"
        assert data["name"] == "Standard"

    @pytest.mark.asyncio
    async def test_get_tier_not_found(self, client):
        conn = _make_async_conn(fetchrow_return=None)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.put(
                "/api/v1/model-access/tiers/nonexistent",
                json={
                    "name": "Updated",
                },
            )

        assert resp.status_code == 404
        assert "Tier not found" in resp.json()["detail"]


# ============================================================================
# Delete Tier
# ============================================================================


class TestDeleteTier:
    """Tests for DELETE /api/v1/model-access/tiers/{id}."""

    @pytest.mark.asyncio
    async def test_delete_tier(self, client):
        conn = _make_async_conn(execute_return="DELETE 1")
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.delete("/api/v1/model-access/tiers/tier-1")

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_delete_tier_not_found(self, client):
        conn = _make_async_conn(execute_return="DELETE 0")
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.delete("/api/v1/model-access/tiers/nonexistent")

        assert resp.status_code == 404
        assert "Tier not found" in resp.json()["detail"]


# ============================================================================
# List Requests
# ============================================================================


class TestListRequests:
    """Tests for GET /api/v1/model-access/requests."""

    @pytest.mark.asyncio
    async def test_list_requests(self, client):
        conn = _make_async_conn(fetch_return=[_request_row])
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/model-access/requests")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "req-1"
        assert data[0]["model_pattern"] == "claude-*"
        assert data[0]["status"] == "pending"


# ============================================================================
# Create Request
# ============================================================================


class TestCreateRequest:
    """Tests for POST /api/v1/model-access/requests."""

    @pytest.mark.asyncio
    async def test_create_request(self, client):
        # First fetchrow checks tier (returns tier_row), second inserts request
        conn = _make_async_conn()
        conn.fetchrow.side_effect = [_tier_row, _request_row]
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.post(
                "/api/v1/model-access/requests",
                json={
                    "model_pattern": "claude-*",
                    "tier_id": "tier-1",
                    "justification": "Need for project",
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "req-1"
        assert data["model_pattern"] == "claude-*"


# ============================================================================
# Approve Request
# ============================================================================


class TestApproveRequest:
    """Tests for POST /api/v1/model-access/requests/{id}/approve."""

    @pytest.mark.asyncio
    async def test_approve_request(self, client):
        # First fetchrow gets the pending request, second gets tier for expiry
        conn = _make_async_conn()
        conn.fetchrow.side_effect = [_request_row, None]
        deps.db_pool = _make_pool(conn)
        deps.http_client = None

        async with client:
            resp = await client.post(
                "/api/v1/model-access/requests/req-1/approve",
                json={
                    "comment": "Approved for Q1",
                },
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    @pytest.mark.asyncio
    async def test_approve_request_not_found(self, client):
        conn = _make_async_conn(fetchrow_return=None)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.post("/api/v1/model-access/requests/nonexistent/approve")

        assert resp.status_code == 404
        assert "Access request not found" in resp.json()["detail"]


# ============================================================================
# Reject Request
# ============================================================================


class TestRejectRequest:
    """Tests for POST /api/v1/model-access/requests/{id}/reject."""

    @pytest.mark.asyncio
    async def test_reject_request(self, client):
        conn = _make_async_conn(fetchrow_return=_request_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.post(
                "/api/v1/model-access/requests/req-1/reject",
                json={
                    "comment": "Insufficient justification",
                },
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
