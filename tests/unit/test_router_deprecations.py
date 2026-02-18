"""Unit tests for the Deprecations router (model deprecation management).

Tests the /api/v1/model-deprecations endpoints.
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

_dep_row = _make_row({
    "id": "dep-1", "model_name": "gpt-3.5-turbo", "replacement_model": "gpt-4o-mini",
    "deprecation_date": "2024-06-01", "sunset_date": "2024-12-01",
    "message": "Use gpt-4o-mini", "created_at": "2024-01-01",
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
# List Deprecations
# ============================================================================


class TestListDeprecations:
    """Tests for GET /api/v1/model-deprecations."""

    @pytest.mark.asyncio
    async def test_list_deprecations(self, client):
        conn = _make_async_conn(fetch_return=[_dep_row])
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/model-deprecations")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "dep-1"
        assert data[0]["model_name"] == "gpt-3.5-turbo"
        assert data[0]["replacement_model"] == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_list_deprecations_no_db(self, client):
        deps.db_pool = None

        async with client:
            resp = await client.get("/api/v1/model-deprecations")

        assert resp.status_code == 503
        assert "Database not available" in resp.json()["detail"]


# ============================================================================
# Create Deprecation
# ============================================================================


class TestCreateDeprecation:
    """Tests for POST /api/v1/model-deprecations."""

    @pytest.mark.asyncio
    async def test_create_deprecation(self, client):
        conn = _make_async_conn(fetchrow_return=_dep_row)
        # First fetchrow checks for duplicate (returns None), second inserts
        conn.fetchrow.side_effect = [None, _dep_row]
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.post("/api/v1/model-deprecations", json={
                "model_name": "gpt-3.5-turbo",
                "replacement_model": "gpt-4o-mini",
                "deprecation_date": "2024-06-01",
                "sunset_date": "2024-12-01",
                "message": "Use gpt-4o-mini",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["model_name"] == "gpt-3.5-turbo"
        assert data["replacement_model"] == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_create_deprecation_duplicate_409(self, client):
        existing_row = _make_row({"id": "dep-existing"})
        conn = _make_async_conn(fetchrow_return=existing_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.post("/api/v1/model-deprecations", json={
                "model_name": "gpt-3.5-turbo",
                "replacement_model": "gpt-4o-mini",
            })

        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]


# ============================================================================
# Check Deprecation
# ============================================================================


class TestCheckDeprecation:
    """Tests for GET /api/v1/model-deprecations/check/{model_name}."""

    @pytest.mark.asyncio
    async def test_check_deprecated(self, client):
        conn = _make_async_conn(fetchrow_return=_dep_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/model-deprecations/check/gpt-3.5-turbo")

        assert resp.status_code == 200
        data = resp.json()
        assert data["deprecated"] is True
        assert data["deprecation"]["model_name"] == "gpt-3.5-turbo"

    @pytest.mark.asyncio
    async def test_check_not_deprecated(self, client):
        conn = _make_async_conn(fetchrow_return=None)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/model-deprecations/check/gpt-4o")

        assert resp.status_code == 200
        data = resp.json()
        assert data["deprecated"] is False


# ============================================================================
# Get Deprecation
# ============================================================================


class TestGetDeprecation:
    """Tests for GET /api/v1/model-deprecations/{deprecation_id}."""

    @pytest.mark.asyncio
    async def test_get_deprecation(self, client):
        conn = _make_async_conn(fetchrow_return=_dep_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/model-deprecations/dep-1")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "dep-1"
        assert data["model_name"] == "gpt-3.5-turbo"

    @pytest.mark.asyncio
    async def test_get_deprecation_not_found(self, client):
        conn = _make_async_conn(fetchrow_return=None)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/model-deprecations/nonexistent")

        assert resp.status_code == 404
        assert "Deprecation not found" in resp.json()["detail"]


# ============================================================================
# Update Deprecation
# ============================================================================


class TestUpdateDeprecation:
    """Tests for PUT /api/v1/model-deprecations/{deprecation_id}."""

    @pytest.mark.asyncio
    async def test_update_deprecation(self, client):
        updated_row = _make_row({
            "id": "dep-1", "model_name": "gpt-3.5-turbo", "replacement_model": "gpt-4o",
            "deprecation_date": "2024-06-01", "sunset_date": "2024-12-01",
            "message": "Use gpt-4o", "created_at": "2024-01-01",
        })
        # First fetchrow checks existing, second returns updated
        conn = _make_async_conn()
        conn.fetchrow.side_effect = [_dep_row, updated_row]
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.put("/api/v1/model-deprecations/dep-1", json={
                "replacement_model": "gpt-4o",
                "message": "Use gpt-4o",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["replacement_model"] == "gpt-4o"


# ============================================================================
# Delete Deprecation
# ============================================================================


class TestDeleteDeprecation:
    """Tests for DELETE /api/v1/model-deprecations/{deprecation_id}."""

    @pytest.mark.asyncio
    async def test_delete_deprecation(self, client):
        conn = _make_async_conn(execute_return="DELETE 1")
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.delete("/api/v1/model-deprecations/dep-1")

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_delete_deprecation_not_found(self, client):
        conn = _make_async_conn(execute_return="DELETE 0")
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.delete("/api/v1/model-deprecations/nonexistent")

        assert resp.status_code == 404
        assert "Deprecation not found" in resp.json()["detail"]


# ============================================================================
# Sync Alias
# ============================================================================


class TestSyncAlias:
    """Tests for POST /api/v1/model-deprecations/{id}/sync-alias."""

    @pytest.mark.asyncio
    async def test_sync_alias_success(self, client):
        conn = _make_async_conn(fetchrow_return=_dep_row)
        deps.db_pool = _make_pool(conn)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"model_id": "new-model-id"}

        http_client = AsyncMock()
        http_client.post.return_value = mock_response
        deps.http_client = http_client

        async with client:
            resp = await client.post("/api/v1/model-deprecations/dep-1/sync-alias")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "synced"
        assert data["model_name"] == "gpt-3.5-turbo"
        assert data["replacement_model"] == "gpt-4o-mini"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
