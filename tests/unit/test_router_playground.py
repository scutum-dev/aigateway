"""Unit tests for the Playground router (playground session management).

Tests the /api/v1/playground/sessions endpoints.
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

_session_row = _make_row(
    {
        "id": "sess-1",
        "name": "Test Session",
        "prompt": "Hello world",
        "models": ["gpt-4o", "claude-3-5-sonnet"],
        "settings": '{"temperature":0.7}',
        "results": "{}",
        "created_by": "test-admin",
        "is_public": False,
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
# List Sessions
# ============================================================================


class TestListSessions:
    """Tests for GET /api/v1/playground/sessions."""

    @pytest.mark.asyncio
    async def test_list_sessions(self, client):
        conn = _make_async_conn(fetch_return=[_session_row])
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/playground/sessions")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "sess-1"
        assert data[0]["name"] == "Test Session"
        assert data[0]["models"] == ["gpt-4o", "claude-3-5-sonnet"]

    @pytest.mark.asyncio
    async def test_list_sessions_no_db(self, client):
        deps.db_pool = None

        async with client:
            resp = await client.get("/api/v1/playground/sessions")

        assert resp.status_code == 503
        assert "Database not available" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_sessions_with_filter(self, client):
        """GET /playground/sessions?created_by=test-admin filters by creator."""
        conn = _make_async_conn(fetch_return=[_session_row])
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/playground/sessions?created_by=test-admin")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["created_by"] == "test-admin"
        # Verify the query used the filter param
        call_args = conn.fetch.call_args
        assert "test-admin" in call_args.args

    @pytest.mark.asyncio
    async def test_list_sessions_public_filter(self, client):
        """GET /playground/sessions?is_public=true filters by public status."""
        conn = _make_async_conn(fetch_return=[])
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/playground/sessions?is_public=true")

        assert resp.status_code == 200
        assert resp.json() == []


# ============================================================================
# Create Session
# ============================================================================


class TestCreateSession:
    """Tests for POST /api/v1/playground/sessions."""

    @pytest.mark.asyncio
    async def test_create_session(self, client):
        conn = _make_async_conn(fetchrow_return=_session_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.post(
                "/api/v1/playground/sessions",
                json={
                    "name": "Test Session",
                    "prompt": "Hello world",
                    "models": ["gpt-4o", "claude-3-5-sonnet"],
                    "settings": {"temperature": 0.7},
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "sess-1"
        assert data["name"] == "Test Session"
        assert data["prompt"] == "Hello world"
        assert data["created_by"] == "test-admin"


# ============================================================================
# Get Session
# ============================================================================


class TestGetSession:
    """Tests for GET /api/v1/playground/sessions/{session_id}."""

    @pytest.mark.asyncio
    async def test_get_session(self, client):
        conn = _make_async_conn(fetchrow_return=_session_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/playground/sessions/sess-1")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "sess-1"
        assert data["prompt"] == "Hello world"
        assert data["settings"] == {"temperature": 0.7}

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, client):
        conn = _make_async_conn(fetchrow_return=None)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/playground/sessions/nonexistent")

        assert resp.status_code == 404
        assert "Session not found" in resp.json()["detail"]


# ============================================================================
# Update Session
# ============================================================================


class TestUpdateSession:
    """Tests for PUT /api/v1/playground/sessions/{session_id}."""

    @pytest.mark.asyncio
    async def test_update_session(self, client):
        updated_row = _make_row(
            {
                "id": "sess-1",
                "name": "Updated Session",
                "prompt": "Updated prompt",
                "models": ["gpt-4o"],
                "settings": '{"temperature":0.5}',
                "results": "{}",
                "created_by": "test-admin",
                "is_public": True,
                "created_at": "2024-01-01",
            }
        )
        # First fetchrow checks existing, second returns updated
        conn = _make_async_conn()
        conn.fetchrow.side_effect = [_session_row, updated_row]
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.put(
                "/api/v1/playground/sessions/sess-1",
                json={
                    "name": "Updated Session",
                    "prompt": "Updated prompt",
                    "is_public": True,
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Session"
        assert data["is_public"] is True

    @pytest.mark.asyncio
    async def test_update_session_not_owner_non_admin(self, client):
        """Non-admin, non-owner cannot update a session."""
        other_user_row = _make_row(
            {
                "id": "sess-1",
                "name": "Test Session",
                "prompt": "Hello world",
                "models": ["gpt-4o"],
                "settings": "{}",
                "results": "{}",
                "created_by": "other-user",
                "is_public": False,
                "created_at": "2024-01-01",
            }
        )
        conn = _make_async_conn(fetchrow_return=other_user_row)
        deps.db_pool = _make_pool(conn)

        # Override to non-admin user
        def _fake_non_admin():
            return UserInfo(user_id="not-the-owner", role="user", is_admin=False)

        app.dependency_overrides[get_current_user] = _fake_non_admin

        async with client:
            resp = await client.put(
                "/api/v1/playground/sessions/sess-1",
                json={
                    "name": "Hacked Session",
                },
            )

        assert resp.status_code == 403
        assert "Not authorized" in resp.json()["detail"]

        # Restore admin override
        app.dependency_overrides[get_current_user] = _fake_user


# ============================================================================
# Delete Session
# ============================================================================


class TestDeleteSession:
    """Tests for DELETE /api/v1/playground/sessions/{session_id}."""

    @pytest.mark.asyncio
    async def test_delete_session(self, client):
        # First fetchrow checks existing, then delete
        conn = _make_async_conn(fetchrow_return=_session_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.delete("/api/v1/playground/sessions/sess-1")

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_delete_session_not_found(self, client):
        conn = _make_async_conn(fetchrow_return=None)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.delete("/api/v1/playground/sessions/nonexistent")

        assert resp.status_code == 404
        assert "Session not found" in resp.json()["detail"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
