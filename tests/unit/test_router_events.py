"""Unit tests for the Events router (DB CRUD).

Tests the /api/v1/events endpoints including subscription CRUD,
event log querying, and test event sending.
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

_sub_row = _make_row({
    "id": "sub-uuid-1", "name": "slack-alerts", "event_types": ["sla.violation"],
    "channel": "slack", "config": '{"webhook_url": "https://hooks.slack.com/test"}',
    "filters": None, "is_active": True, "created_at": "2024-01-01T00:00:00",
})

_event_row = _make_row({
    "id": "evt-uuid-1", "event_type": "sla.violation",
    "payload": '{"message": "test"}', "source_service": "admin-api",
    "created_at": "2024-01-01T00:00:00",
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
# Subscription CRUD
# ============================================================================


class TestSubscriptions:
    """Tests for /api/v1/events/subscriptions endpoints."""

    @pytest.mark.asyncio
    async def test_list_subscriptions(self, client):
        """GET /events/subscriptions returns list from DB."""
        conn = _make_async_conn(fetch_return=[_sub_row])
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/events/subscriptions")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "slack-alerts"
        assert data[0]["channel"] == "slack"
        assert data[0]["event_types"] == ["sla.violation"]
        assert data[0]["is_active"] is True

    @pytest.mark.asyncio
    async def test_list_subscriptions_no_db(self, client):
        """GET /events/subscriptions returns 503 when DB is unavailable."""
        deps.db_pool = None

        async with client:
            resp = await client.get("/api/v1/events/subscriptions")

        assert resp.status_code == 503
        assert "Database not available" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_subscription(self, client):
        """POST /events/subscriptions creates subscription."""
        conn = _make_async_conn(fetchrow_return=_sub_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.post("/api/v1/events/subscriptions", json={
                "name": "slack-alerts",
                "event_types": ["sla.violation"],
                "channel": "slack",
                "config": {"webhook_url": "https://hooks.slack.com/test"},
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "slack-alerts"
        assert data["id"] == "sub-uuid-1"
        assert data["channel"] == "slack"
        conn.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_subscription(self, client):
        """GET /events/subscriptions/{id} returns subscription when found."""
        conn = _make_async_conn(fetchrow_return=_sub_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/events/subscriptions/sub-uuid-1")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "sub-uuid-1"
        assert data["name"] == "slack-alerts"

    @pytest.mark.asyncio
    async def test_get_subscription_not_found(self, client):
        """GET /events/subscriptions/{id} returns 404 when not found."""
        conn = _make_async_conn(fetchrow_return=None)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/events/subscriptions/nonexistent")

        assert resp.status_code == 404
        assert "Subscription not found" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_subscription(self, client):
        """PUT /events/subscriptions/{id} updates subscription."""
        updated_sub = _make_row({
            "id": "sub-uuid-1", "name": "slack-alerts-updated",
            "event_types": ["sla.violation", "budget.exceeded"],
            "channel": "slack",
            "config": '{"webhook_url": "https://hooks.slack.com/updated"}',
            "filters": None, "is_active": True, "created_at": "2024-01-01T00:00:00",
        })
        # First fetchrow returns existing, second returns updated
        conn = _make_async_conn()
        conn.fetchrow.side_effect = [_sub_row, updated_sub]
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.put("/api/v1/events/subscriptions/sub-uuid-1", json={
                "name": "slack-alerts-updated",
                "event_types": ["sla.violation", "budget.exceeded"],
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "slack-alerts-updated"

    @pytest.mark.asyncio
    async def test_update_subscription_not_found(self, client):
        """PUT /events/subscriptions/{id} returns 404 when not found."""
        conn = _make_async_conn(fetchrow_return=None)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.put("/api/v1/events/subscriptions/nonexistent", json={
                "name": "updated",
            })

        assert resp.status_code == 404
        assert "Subscription not found" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_delete_subscription(self, client):
        """DELETE /events/subscriptions/{id} deletes subscription."""
        conn = _make_async_conn(execute_return="DELETE 1")
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.delete("/api/v1/events/subscriptions/sub-uuid-1")

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_delete_subscription_not_found(self, client):
        """DELETE /events/subscriptions/{id} returns 404 when not found."""
        conn = _make_async_conn(execute_return="DELETE 0")
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.delete("/api/v1/events/subscriptions/nonexistent")

        assert resp.status_code == 404
        assert "Subscription not found" in resp.json()["detail"]


# ============================================================================
# Event Log
# ============================================================================


class TestEventLog:
    """Tests for /api/v1/events/log endpoints."""

    @pytest.mark.asyncio
    async def test_list_events(self, client):
        """GET /events/log returns event list from DB."""
        conn = _make_async_conn(fetch_return=[_event_row])
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/events/log")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "evt-uuid-1"
        assert data[0]["event_type"] == "sla.violation"
        assert data[0]["payload"] == {"message": "test"}
        assert data[0]["source_service"] == "admin-api"

    @pytest.mark.asyncio
    async def test_list_events_with_filter(self, client):
        """GET /events/log?event_type=sla.violation filters by type."""
        conn = _make_async_conn(fetch_return=[_event_row])
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/events/log?event_type=sla.violation")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        # Verify filter parameter was passed
        call_args = conn.fetch.call_args
        assert "sla.violation" in call_args.args

    @pytest.mark.asyncio
    async def test_list_events_no_db(self, client):
        """GET /events/log returns 503 when DB is unavailable."""
        deps.db_pool = None

        async with client:
            resp = await client.get("/api/v1/events/log")

        assert resp.status_code == 503
        assert "Database not available" in resp.json()["detail"]


# ============================================================================
# Test Event
# ============================================================================


class TestSendTestEvent:
    """Tests for POST /api/v1/events/test."""

    @pytest.mark.asyncio
    async def test_send_test_event(self, client):
        """POST /events/test inserts event into event_log."""
        conn = _make_async_conn(fetchrow_return=_event_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.post("/api/v1/events/test", json={
                "event_type": "sla.violation",
                "payload": {"message": "test"},
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "evt-uuid-1"
        assert data["event_type"] == "sla.violation"
        assert data["source_service"] == "admin-api"
        conn.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_test_event_no_db(self, client):
        """POST /events/test returns 503 when DB is unavailable."""
        deps.db_pool = None

        async with client:
            resp = await client.post("/api/v1/events/test", json={
                "event_type": "sla.violation",
                "payload": {"message": "test"},
            })

        assert resp.status_code == 503
        assert "Database not available" in resp.json()["detail"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
