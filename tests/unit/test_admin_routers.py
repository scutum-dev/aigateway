"""Unit tests for the Admin API router modules.

Tests Settings router by:
1. Loading admin-api modules via importlib (same pattern as test_auth.py)
2. Mocking deps.db_pool, deps.http_client, deps.redis_client before each test
3. Using httpx.ASGITransport to test the full FastAPI app
4. Overriding auth dependencies to bypass JWT validation
"""

import importlib.util
import os
import sys
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

# ---------------------------------------------------------------------------
# Module loading (mirrors test_auth.py pattern)
# ---------------------------------------------------------------------------

_service_dir = os.path.join(os.path.dirname(__file__), "../../src/admin-api")
sys.path.insert(0, _service_dir)

# We need to pre-mock heavy dependencies that main.py imports at module level
# so the import does not fail when those packages are not installed or when
# side-effects (like OTEL tracer setup) fire.

# Mock opentelemetry modules before importing main
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

# Mock alembic so migrations don't run
_alembic_mock = MagicMock()
sys.modules.setdefault("alembic", _alembic_mock)
sys.modules.setdefault("alembic.config", _alembic_mock)
sys.modules.setdefault("alembic.command", _alembic_mock)

# Now import the admin-api modules
_spec = importlib.util.spec_from_file_location("admin_api_main", os.path.join(_service_dir, "main.py"))
_main_mod = importlib.util.module_from_spec(_spec)
sys.modules["admin_api_main"] = _main_mod
_spec.loader.exec_module(_main_mod)

app = _main_mod.app

# Import deps and auth from the already-loaded service path
import deps  # noqa: E402
from auth import UserInfo, get_current_user, require_admin  # noqa: E402

# ---------------------------------------------------------------------------
# Auth override -- bypass JWT for all endpoints
# ---------------------------------------------------------------------------


def _fake_user():
    return UserInfo(user_id="test-admin", role="admin", is_admin=True)


app.dependency_overrides[get_current_user] = _fake_user
app.dependency_overrides[require_admin] = _fake_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_async_conn(
    fetch_return=None,
    fetchrow_return=None,
    execute_return=None,
):
    """Build a mock asyncpg connection with configurable return values."""
    conn = AsyncMock()
    conn.fetch.return_value = fetch_return if fetch_return is not None else []
    conn.fetchrow.return_value = fetchrow_return
    conn.execute.return_value = execute_return or "DELETE 1"
    return conn


def _make_pool(conn):
    """Wrap a mock connection in a pool that supports `async with pool.acquire()`."""
    pool = MagicMock()
    ctx = AsyncMock()
    ctx.__aenter__.return_value = conn
    ctx.__aexit__.return_value = None
    pool.acquire.return_value = ctx
    return pool


@pytest.fixture(autouse=True)
def _reset_deps():
    """Ensure deps state is clean before and after each test."""
    original_pool = deps.db_pool
    original_http = deps.http_client
    original_redis = deps.redis_client

    # Reset the rate-limit cache so it doesn't bleed across tests
    _main_mod._rate_limit_cache["value"] = 0
    _main_mod._rate_limit_cache["expires_at"] = 9999999999.0
    _main_mod._inmemory_requests.clear()

    yield

    deps.db_pool = original_pool
    deps.http_client = original_http
    deps.redis_client = original_redis


# ---------------------------------------------------------------------------
# Client helper
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """Return an httpx.AsyncClient wired to the FastAPI app."""
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# ============================================================================
# Settings Router
# ============================================================================


class TestSettingsRouter:
    """Tests for /api/v1/settings endpoints."""

    @pytest.mark.asyncio
    async def test_get_settings(self, client):
        """GET /settings returns settings from DB."""
        rows = [
            {"key": "default_model", "value": "claude-3-5-sonnet"},
            {"key": "enable_caching", "value": "false"},
        ]
        conn = _make_async_conn(fetch_return=rows)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/settings")

        assert resp.status_code == 200
        data = resp.json()
        assert data["default_model"] == "claude-3-5-sonnet"
        assert data["enable_caching"] == "false"

    @pytest.mark.asyncio
    async def test_get_settings_no_db(self, client):
        """GET /settings returns defaults when DB pool is None."""
        deps.db_pool = None

        async with client:
            resp = await client.get("/api/v1/settings")

        assert resp.status_code == 200
        data = resp.json()
        # Should be PlatformSettings defaults
        assert data["default_model"] == "gpt-4o-mini"
        assert data["enable_caching"] is True

    @pytest.mark.asyncio
    async def test_update_settings(self, client):
        """PUT /settings writes to DB and returns settings."""
        conn = _make_async_conn()
        deps.db_pool = _make_pool(conn)

        settings_payload = {
            "default_model": "gpt-4o",
            "global_rate_limit": 500,
            "enable_caching": False,
            "cache_ttl_seconds": 1800,
            "enable_cost_tracking": True,
            "enable_budget_enforcement": True,
            "enable_guardrails": True,
            "maintenance_mode": False,
        }

        async with client:
            resp = await client.put(
                "/api/v1/settings",
                json=settings_payload,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["default_model"] == "gpt-4o"
        assert data["enable_caching"] is False
        # Verify conn.execute was called for each setting key
        assert conn.execute.call_count == len(settings_payload)

    @pytest.mark.asyncio
    async def test_update_settings_no_db(self, client):
        """PUT /settings returns 503 when DB is unavailable."""
        deps.db_pool = None

        async with client:
            resp = await client.put(
                "/api/v1/settings",
                json={"default_model": "gpt-4o"},
            )

        assert resp.status_code == 503


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
