"""Unit tests for the Audit router (DB CRUD).

Tests the /api/v1/audit-logs endpoints including list with filters
and CSV/JSON export.
"""

import importlib.util
import json
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
    """Create a dict-like mock row that supports both row['key'] and row.get('key')."""
    row = MagicMock()
    row.__getitem__ = lambda self, key: data[key]
    row.__contains__ = lambda self, key: key in data
    row.get = lambda key, default=None: data.get(key, default)
    row.keys = lambda: data.keys()
    return row


def _make_async_conn(fetch_return=None, fetchrow_return=None, execute_return=None):
    conn = AsyncMock()
    conn.fetch.return_value = fetch_return if fetch_return is not None else []
    conn.fetchrow.return_value = fetchrow_return
    conn.execute.return_value = execute_return or "DELETE 1"
    conn.fetchval.return_value = None
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

_audit_row = _make_row(
    {
        "id": "audit-uuid-1",
        "timestamp": "2024-01-01T00:00:00",
        "actor_id": "admin",
        "actor_email": "admin@test.com",
        "actor_ip": "127.0.0.1",
        "org_id": None,
        "action": "create",
        "resource_type": "organization",
        "resource_id": "org-1",
        "resource_name": "Test Org",
        "changes": "{}",
        "request_metadata": "{}",
        "created_at": "2024-01-01T00:00:00",
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
# List Audit Logs
# ============================================================================


class TestListAuditLogs:
    """Tests for GET /api/v1/audit-logs."""

    @pytest.mark.asyncio
    async def test_list_audit_logs(self, client):
        """GET /audit-logs returns list from DB."""
        conn = _make_async_conn(fetch_return=[_audit_row])
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/audit-logs")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "audit-uuid-1"
        assert data[0]["actor_id"] == "admin"
        assert data[0]["action"] == "create"
        assert data[0]["resource_type"] == "organization"

    @pytest.mark.asyncio
    async def test_list_audit_logs_with_actor_filter(self, client):
        """GET /audit-logs?actor_id=admin filters by actor."""
        conn = _make_async_conn(fetch_return=[_audit_row])
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/audit-logs?actor_id=admin")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["actor_id"] == "admin"
        # Verify the query was called with the actor_id param
        call_args = conn.fetch.call_args
        assert "admin" in call_args.args

    @pytest.mark.asyncio
    async def test_list_audit_logs_with_action_filter(self, client):
        """GET /audit-logs?action=create filters by action."""
        conn = _make_async_conn(fetch_return=[_audit_row])
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/audit-logs?action=create")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        call_args = conn.fetch.call_args
        assert "create" in call_args.args

    @pytest.mark.asyncio
    async def test_list_audit_logs_with_resource_type(self, client):
        """GET /audit-logs?resource_type=organization filters by resource type."""
        conn = _make_async_conn(fetch_return=[_audit_row])
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/audit-logs?resource_type=organization")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        call_args = conn.fetch.call_args
        assert "organization" in call_args.args

    @pytest.mark.asyncio
    async def test_list_audit_logs_with_pagination(self, client):
        """GET /audit-logs?limit=10&offset=5 passes pagination params."""
        conn = _make_async_conn(fetch_return=[])
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/audit-logs?limit=10&offset=5")

        assert resp.status_code == 200
        call_args = conn.fetch.call_args
        # limit=10 and offset=5 should be in the args
        assert 10 in call_args.args
        assert 5 in call_args.args

    @pytest.mark.asyncio
    async def test_list_audit_logs_no_db(self, client):
        """GET /audit-logs returns 503 when DB is unavailable."""
        deps.db_pool = None

        async with client:
            resp = await client.get("/api/v1/audit-logs")

        assert resp.status_code == 503
        assert "Database not available" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_audit_logs_empty(self, client):
        """GET /audit-logs returns empty list when no results."""
        conn = _make_async_conn(fetch_return=[])
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/audit-logs")

        assert resp.status_code == 200
        assert resp.json() == []


# ============================================================================
# Export Audit Logs
# ============================================================================


class TestExportAuditLogs:
    """Tests for GET /api/v1/audit-logs/export."""

    @pytest.mark.asyncio
    async def test_export_csv(self, client):
        """GET /audit-logs/export?format=csv returns CSV content."""
        conn = _make_async_conn(fetch_return=[_audit_row])
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/audit-logs/export?format=csv")

        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")
        body = resp.text
        # CSV header row
        assert "id" in body
        assert "actor_id" in body
        assert "action" in body
        # Data row
        assert "audit-uuid-1" in body
        assert "admin" in body
        assert "create" in body

    @pytest.mark.asyncio
    async def test_export_json(self, client):
        """GET /audit-logs/export?format=json returns JSON content."""
        conn = _make_async_conn(fetch_return=[_audit_row])
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/audit-logs/export?format=json")

        assert resp.status_code == 200
        assert "application/json" in resp.headers.get("content-type", "")
        data = json.loads(resp.text)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == "audit-uuid-1"
        assert data[0]["action"] == "create"

    @pytest.mark.asyncio
    async def test_export_no_db(self, client):
        """GET /audit-logs/export returns 503 when DB is unavailable."""
        deps.db_pool = None

        async with client:
            resp = await client.get("/api/v1/audit-logs/export?format=csv")

        assert resp.status_code == 503
        assert "Database not available" in resp.json()["detail"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
