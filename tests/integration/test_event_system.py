"""Integration tests for the event subscription and event log system.

Tests the full event pipeline: subscription CRUD, event log querying,
test event sending, pagination, and error handling.
"""

import importlib.util
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

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
import deps
from auth import UserInfo, get_current_user, require_admin


def _fake_user():
    return UserInfo(user_id="test-admin", role="admin", is_admin=True)


app.dependency_overrides[get_current_user] = _fake_user
app.dependency_overrides[require_admin] = _fake_user


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


def _subscription_row(overrides=None):
    """Return a base event subscription row dict."""
    base = {
        "id": "sub-001",
        "name": "Budget Alerts",
        "event_types": ["budget.exceeded", "budget.warning"],
        "channel": "webhook",
        "config": json.dumps({"url": "https://hooks.example.com/budget"}),
        "filters": None,
        "is_active": True,
        "created_at": "2026-01-01T00:00:00",
    }
    if overrides:
        base.update(overrides)
    return base


def _event_row(overrides=None):
    """Return a base event log row dict."""
    base = {
        "id": "evt-001",
        "event_type": "budget.exceeded",
        "payload": json.dumps({"team_id": "team-1", "budget": 100, "spent": 120}),
        "source_service": "budget-webhook",
        "created_at": "2026-01-15T12:00:00",
    }
    if overrides:
        base.update(overrides)
    return base


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
# 1. Create subscription
# ============================================================================


@pytest.mark.asyncio
async def test_create_subscription(client):
    """POST /events/subscriptions creates a new event subscription."""
    row = _make_row(_subscription_row())
    conn = _make_async_conn(fetchrow_return=row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post("/api/v1/events/subscriptions", json={
            "name": "Budget Alerts",
            "event_types": ["budget.exceeded", "budget.warning"],
            "channel": "webhook",
            "config": {"url": "https://hooks.example.com/budget"},
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Budget Alerts"
    assert data["channel"] == "webhook"
    assert "budget.exceeded" in data["event_types"]


# ============================================================================
# 2. List subscriptions
# ============================================================================


@pytest.mark.asyncio
async def test_list_subscriptions(client):
    """GET /events/subscriptions returns all subscriptions."""
    sub1 = _make_row(_subscription_row({"id": "sub-1", "name": "Alerts"}))
    sub2 = _make_row(_subscription_row({"id": "sub-2", "name": "Slack Notifs", "channel": "slack"}))
    conn = _make_async_conn(fetch_return=[sub1, sub2])
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/events/subscriptions")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["name"] == "Alerts"
    assert data[1]["channel"] == "slack"


# ============================================================================
# 3. Get subscription
# ============================================================================


@pytest.mark.asyncio
async def test_get_subscription(client):
    """GET /events/subscriptions/{id} returns a specific subscription."""
    row = _make_row(_subscription_row())
    conn = _make_async_conn(fetchrow_return=row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/events/subscriptions/sub-001")

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "sub-001"
    assert data["name"] == "Budget Alerts"


# ============================================================================
# 4. Update subscription
# ============================================================================


@pytest.mark.asyncio
async def test_update_subscription(client):
    """PUT /events/subscriptions/{id} updates subscription fields."""
    existing_row = _make_row(_subscription_row())
    updated_row = _make_row(_subscription_row({"name": "Updated Alerts", "channel": "slack"}))

    conn = _make_async_conn()
    conn.fetchrow = AsyncMock(side_effect=[existing_row, updated_row])
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.put("/api/v1/events/subscriptions/sub-001", json={
            "name": "Updated Alerts",
            "channel": "slack",
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated Alerts"
    assert data["channel"] == "slack"


# ============================================================================
# 5. Delete subscription
# ============================================================================


@pytest.mark.asyncio
async def test_delete_subscription(client):
    """DELETE /events/subscriptions/{id} removes a subscription."""
    conn = _make_async_conn(execute_return="DELETE 1")
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.delete("/api/v1/events/subscriptions/sub-001")

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ============================================================================
# 6. List events log
# ============================================================================


@pytest.mark.asyncio
async def test_list_events_log(client):
    """GET /events/log returns event entries."""
    evt1 = _make_row(_event_row({"id": "evt-1"}))
    evt2 = _make_row(_event_row({"id": "evt-2", "event_type": "budget.warning"}))
    conn = _make_async_conn(fetch_return=[evt1, evt2])
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/events/log")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["event_type"] == "budget.exceeded"
    assert data[1]["event_type"] == "budget.warning"


# ============================================================================
# 7. List events with type filter
# ============================================================================


@pytest.mark.asyncio
async def test_list_events_with_type_filter(client):
    """GET /events/log?event_type=budget.exceeded filters events."""
    evt = _make_row(_event_row({"event_type": "budget.exceeded"}))
    conn = _make_async_conn(fetch_return=[evt])
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/events/log", params={"event_type": "budget.exceeded"})

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["event_type"] == "budget.exceeded"

    # Verify the fetch was called with event_type parameter
    call_args = conn.fetch.call_args[0]
    sql = call_args[0]
    assert "event_type" in sql.lower()


# ============================================================================
# 8. Send test event
# ============================================================================


@pytest.mark.asyncio
async def test_send_test_event(client):
    """POST /events/test inserts a test event into event_log."""
    evt_row = _make_row(_event_row({
        "event_type": "test.ping",
        "payload": json.dumps({"message": "hello"}),
        "source_service": "admin-api-test",
    }))
    conn = _make_async_conn(fetchrow_return=evt_row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post("/api/v1/events/test", json={
            "event_type": "test.ping",
            "payload": {"message": "hello"},
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["event_type"] == "test.ping"
    assert data["source_service"] == "admin-api-test"


# ============================================================================
# 9. Subscription not found
# ============================================================================


@pytest.mark.asyncio
async def test_subscription_not_found(client):
    """GET /events/subscriptions/{id} returns 404 for missing subscription."""
    conn = _make_async_conn(fetchrow_return=None)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/events/subscriptions/nonexistent")

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ============================================================================
# 10. Update subscription not found
# ============================================================================


@pytest.mark.asyncio
async def test_update_subscription_not_found(client):
    """PUT /events/subscriptions/{id} returns 404 for missing subscription."""
    conn = _make_async_conn(fetchrow_return=None)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.put("/api/v1/events/subscriptions/nonexistent", json={
            "name": "Updated",
        })

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ============================================================================
# 11. Delete subscription not found
# ============================================================================


@pytest.mark.asyncio
async def test_delete_subscription_not_found(client):
    """DELETE /events/subscriptions/{id} returns 404 for missing subscription."""
    conn = _make_async_conn(execute_return="DELETE 0")
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.delete("/api/v1/events/subscriptions/nonexistent")

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ============================================================================
# 12. List events pagination
# ============================================================================


@pytest.mark.asyncio
async def test_list_events_pagination(client):
    """GET /events/log?limit=2&offset=1 applies pagination parameters."""
    evt = _make_row(_event_row())
    conn = _make_async_conn(fetch_return=[evt])
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/events/log", params={"limit": 2, "offset": 1})

    assert resp.status_code == 200
    # Verify that limit and offset were passed to the query
    call_args = conn.fetch.call_args[0]
    # The limit and offset should be in the positional arguments
    assert 2 in call_args
    assert 1 in call_args


# ============================================================================
# 13. List subscriptions no DB
# ============================================================================


@pytest.mark.asyncio
async def test_list_subscriptions_no_db(client):
    """GET /events/subscriptions returns 503 when db_pool is None."""
    deps.db_pool = None

    async with client:
        resp = await client.get("/api/v1/events/subscriptions")

    assert resp.status_code == 503
    assert "Database not available" in resp.json()["detail"]


# ============================================================================
# 14. Send test event no DB
# ============================================================================


@pytest.mark.asyncio
async def test_send_test_event_no_db(client):
    """POST /events/test returns 503 when db_pool is None."""
    deps.db_pool = None

    async with client:
        resp = await client.post("/api/v1/events/test", json={
            "event_type": "test.ping",
            "payload": {"message": "hello"},
        })

    assert resp.status_code == 503
    assert "Database not available" in resp.json()["detail"]


# ============================================================================
# 15. Event log empty results
# ============================================================================


@pytest.mark.asyncio
async def test_event_log_empty_results(client):
    """GET /events/log returns empty list when no events exist."""
    conn = _make_async_conn(fetch_return=[])
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/events/log")

    assert resp.status_code == 200
    assert resp.json() == []
