"""Unit tests for the Cache router (DB CRUD).

Tests the /api/v1/cache endpoints including stats, entries,
settings, lookup, store, and clear operations.
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

_cache_entry_row = _make_row(
    {
        "id": "cache-uuid-1",
        "prompt_hash": "abc123hash",
        "model": "gpt-4o",
        "token_count": 150,
        "hit_count": 5,
        "last_hit_at": "2024-01-01T12:00:00",
        "created_at": "2024-01-01T00:00:00",
        "expires_at": "2024-01-02T00:00:00",
    }
)

_stats_row = _make_row(
    {
        "total_entries": 100,
        "total_hits": 50,
        "avg_token_count": 200.0,
    }
)

_size_row = _make_row(
    {
        "size_bytes": 1048576,  # 1 MB
    }
)

_setting_row = _make_row(
    {
        "value": '"true"',
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
# Cache Stats
# ============================================================================


class TestCacheStats:
    """Tests for GET /api/v1/cache/stats."""

    @pytest.mark.asyncio
    async def test_get_cache_stats(self, client):
        """GET /cache/stats returns stats when table exists."""
        conn = _make_async_conn()
        # fetchval returns True (table exists)
        conn.fetchval.return_value = True
        # fetchrow returns stats then size
        conn.fetchrow.side_effect = [_stats_row, _size_row]
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/cache/stats")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_entries"] == 100
        assert data["total_hits"] == 50
        assert data["cache_size_mb"] == 1.0
        assert data["avg_token_savings"] == 200.0
        # hit_rate = 50 / (50 + 100) * 100 = 33.33
        assert data["hit_rate"] == 33.33

    @pytest.mark.asyncio
    async def test_get_cache_stats_no_table(self, client):
        """GET /cache/stats returns zeros when table does not exist."""
        conn = _make_async_conn()
        conn.fetchval.return_value = False
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/cache/stats")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_entries"] == 0
        assert data["total_hits"] == 0
        assert data["hit_rate"] == 0.0
        assert data["cache_size_mb"] == 0.0
        assert data["avg_token_savings"] == 0.0

    @pytest.mark.asyncio
    async def test_get_cache_stats_no_db(self, client):
        """GET /cache/stats returns 503 when DB is unavailable."""
        deps.db_pool = None

        async with client:
            resp = await client.get("/api/v1/cache/stats")

        assert resp.status_code == 503
        assert "Database not available" in resp.json()["detail"]


# ============================================================================
# Cache Entries
# ============================================================================


class TestCacheEntries:
    """Tests for GET /api/v1/cache/entries."""

    @pytest.mark.asyncio
    async def test_list_cache_entries(self, client):
        """GET /cache/entries returns entries when table exists."""
        conn = _make_async_conn()
        conn.fetchval.return_value = True
        conn.fetch.return_value = [_cache_entry_row]
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/cache/entries")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "cache-uuid-1"
        assert data[0]["model"] == "gpt-4o"
        assert data[0]["hit_count"] == 5
        assert data[0]["token_count"] == 150

    @pytest.mark.asyncio
    async def test_list_cache_entries_no_table(self, client):
        """GET /cache/entries returns empty list when table does not exist."""
        conn = _make_async_conn()
        conn.fetchval.return_value = False
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/cache/entries")

        assert resp.status_code == 200
        assert resp.json() == []


# ============================================================================
# Cache Settings
# ============================================================================


class TestCacheSettings:
    """Tests for /api/v1/cache/settings endpoints."""

    @pytest.mark.asyncio
    async def test_get_cache_settings(self, client):
        """GET /cache/settings returns current settings."""
        conn = _make_async_conn()
        # _get_cache_setting calls fetchrow for each setting key;
        # return None to use defaults
        conn.fetchrow.return_value = None
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/cache/settings")

        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is True
        assert data["similarity_threshold"] == 0.92
        assert data["ttl_seconds"] == 3600
        assert data["max_entries"] == 10000

    @pytest.mark.asyncio
    async def test_update_cache_settings(self, client):
        """PUT /cache/settings updates settings and returns them."""
        conn = _make_async_conn()
        deps.db_pool = _make_pool(conn)
        # No http_client to avoid LiteLLM sync
        deps.http_client = None

        async with client:
            resp = await client.put(
                "/api/v1/cache/settings",
                json={
                    "enabled": False,
                    "similarity_threshold": 0.85,
                    "ttl_seconds": 7200,
                    "max_entries": 5000,
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is False
        assert data["similarity_threshold"] == 0.85
        assert data["ttl_seconds"] == 7200
        assert data["max_entries"] == 5000
        # Verify execute was called for each setting (4 upserts)
        assert conn.execute.call_count == 4


# ============================================================================
# Clear Cache
# ============================================================================


class TestClearCache:
    """Tests for POST /api/v1/cache/clear."""

    @pytest.mark.asyncio
    async def test_clear_cache(self, client):
        """POST /cache/clear deletes all entries."""
        conn = _make_async_conn()
        conn.fetchval.return_value = True
        conn.execute.return_value = "DELETE 42"
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.post("/api/v1/cache/clear")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["deleted"] == 42

    @pytest.mark.asyncio
    async def test_clear_cache_no_table(self, client):
        """POST /cache/clear returns deleted=0 when table does not exist."""
        conn = _make_async_conn()
        conn.fetchval.return_value = False
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.post("/api/v1/cache/clear")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["deleted"] == 0


# ============================================================================
# Delete Cache Entry
# ============================================================================


class TestDeleteCacheEntry:
    """Tests for DELETE /api/v1/cache/entries/{entry_id}."""

    @pytest.mark.asyncio
    async def test_delete_cache_entry(self, client):
        """DELETE /cache/entries/{id} deletes a single entry."""
        conn = _make_async_conn(execute_return="DELETE 1")
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.delete("/api/v1/cache/entries/cache-uuid-1")

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_delete_cache_entry_not_found(self, client):
        """DELETE /cache/entries/{id} returns 404 when not found."""
        conn = _make_async_conn(execute_return="DELETE 0")
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.delete("/api/v1/cache/entries/nonexistent")

        assert resp.status_code == 404
        assert "Cache entry not found" in resp.json()["detail"]


# ============================================================================
# Cache Lookup
# ============================================================================


class TestCacheLookup:
    """Tests for POST /api/v1/cache/lookup."""

    @pytest.mark.asyncio
    async def test_cache_lookup_no_db(self, client):
        """POST /cache/lookup returns 503 when DB is unavailable."""
        deps.db_pool = None

        async with client:
            resp = await client.post(
                "/api/v1/cache/lookup",
                json={
                    "prompt": "What is AI?",
                },
            )

        assert resp.status_code == 503
        assert "Database not available" in resp.json()["detail"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
