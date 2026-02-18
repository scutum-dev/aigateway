"""Unit tests for the A/B Tests router.

Tests CRUD operations, lifecycle (start/stop/promote), snapshots,
metrics collection, and the _is_variant_better helper function.
"""

import importlib.util
import os
import sys
from unittest.mock import AsyncMock, MagicMock

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

import deps  # noqa: E402
from auth import UserInfo, get_current_user, require_admin  # noqa: E402


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


# ---------------------------------------------------------------------------
# Shared mock data
# ---------------------------------------------------------------------------

_ab_test_row = _make_row({
    "id": "test-uuid-1", "name": "GPT4o vs Claude", "status": "draft",
    "base_model": "gpt-4o", "variant_model": "claude-3-5-sonnet",
    "traffic_split_percent": 10, "success_metric": "cost_efficiency",
    "promotion_threshold": None, "rollback_threshold": None,
    "auto_promote": False, "auto_rollback": True,
    "started_at": None, "completed_at": None, "created_by": "admin",
    "created_at": "2024-01-01T00:00:00",
})

_snapshot_row = _make_row({
    "id": "snap-uuid-1", "test_id": "test-uuid-1",
    "snapshot_at": "2024-01-02T00:00:00",
    "base_metrics": '{"avg_latency_ms": 300, "avg_cost": 0.05}',
    "variant_metrics": '{"avg_latency_ms": 250, "avg_cost": 0.04}',
    "recommendation": "promote",
})


# ============================================================================
# CRUD Tests
# ============================================================================


@pytest.mark.asyncio
async def test_list_ab_tests(client):
    """GET /ab-tests returns all A/B tests."""
    conn = _make_async_conn(fetch_return=[_ab_test_row])
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/ab-tests")

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["name"] == "GPT4o vs Claude"
    assert data[0]["status"] == "draft"


@pytest.mark.asyncio
async def test_list_ab_tests_no_db(client):
    """GET /ab-tests returns 503 when database is unavailable."""
    deps.db_pool = None

    async with client:
        resp = await client.get("/api/v1/ab-tests")

    assert resp.status_code == 503
    assert "Database not available" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_ab_test(client):
    """POST /ab-tests creates a new A/B test."""
    conn = _make_async_conn(fetchrow_return=_ab_test_row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post("/api/v1/ab-tests", json={
            "name": "GPT4o vs Claude",
            "base_model": "gpt-4o",
            "variant_model": "claude-3-5-sonnet",
            "traffic_split_percent": 10,
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "GPT4o vs Claude"
    assert data["base_model"] == "gpt-4o"
    conn.fetchrow.assert_called_once()


@pytest.mark.asyncio
async def test_get_ab_test(client):
    """GET /ab-tests/{test_id} returns a test with its latest snapshot."""
    conn = _make_async_conn()
    # First fetchrow returns the test, second returns the snapshot
    conn.fetchrow.side_effect = [_ab_test_row, _snapshot_row]
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/ab-tests/test-uuid-1")

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "test-uuid-1"
    assert data["latest_snapshot"] is not None
    assert data["latest_snapshot"]["recommendation"] == "promote"


@pytest.mark.asyncio
async def test_get_ab_test_not_found(client):
    """GET /ab-tests/{test_id} returns 404 for nonexistent test."""
    conn = _make_async_conn(fetchrow_return=None)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/ab-tests/nonexistent-uuid")

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_ab_test(client):
    """PUT /ab-tests/{test_id} updates the test."""
    updated_row = _make_row({
        **{k: _ab_test_row[k] for k in _ab_test_row.keys()},
        "name": "Updated Name",
    })
    conn = _make_async_conn(fetchrow_return=updated_row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.put("/api/v1/ab-tests/test-uuid-1", json={
            "name": "Updated Name",
        })

    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_update_ab_test_not_found(client):
    """PUT /ab-tests/{test_id} returns 404 when test doesn't exist."""
    conn = _make_async_conn(fetchrow_return=None)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.put("/api/v1/ab-tests/nonexistent-uuid", json={
            "name": "Updated Name",
        })

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_ab_test(client):
    """DELETE /ab-tests/{test_id} removes the test."""
    conn = _make_async_conn(execute_return="DELETE 1")
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.delete("/api/v1/ab-tests/test-uuid-1")

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_delete_ab_test_not_found(client):
    """DELETE /ab-tests/{test_id} returns 404 for nonexistent test."""
    conn = _make_async_conn(execute_return="DELETE 0")
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.delete("/api/v1/ab-tests/nonexistent-uuid")

    assert resp.status_code == 404


# ============================================================================
# Lifecycle Tests
# ============================================================================


@pytest.mark.asyncio
async def test_start_ab_test(client):
    """POST /ab-tests/{test_id}/start transitions draft to running."""
    running_row = _make_row({
        **{k: _ab_test_row[k] for k in _ab_test_row.keys()},
        "status": "running",
        "started_at": "2024-01-02T00:00:00",
    })
    conn = _make_async_conn()
    # fetchrow: first call returns draft test, second returns updated running test
    conn.fetchrow.side_effect = [_ab_test_row, running_row]
    deps.db_pool = _make_pool(conn)

    # Mock LiteLLM integration (http_client used by _add_variant_to_litellm)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"model_info": {"id": "litellm-model-123"}}
    deps.http_client = AsyncMock()
    deps.http_client.post = AsyncMock(return_value=mock_resp)

    async with client:
        resp = await client.post("/api/v1/ab-tests/test-uuid-1/start")

    assert resp.status_code == 200
    assert resp.json()["status"] == "running"
    # Verify LiteLLM was called to add the variant
    deps.http_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_start_ab_test_invalid_status(client):
    """POST /ab-tests/{test_id}/start returns 400 when test is already running."""
    running_test = _make_row({
        **{k: _ab_test_row[k] for k in _ab_test_row.keys()},
        "status": "running",
    })
    conn = _make_async_conn(fetchrow_return=running_test)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post("/api/v1/ab-tests/test-uuid-1/start")

    assert resp.status_code == 400
    assert "Cannot start" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_stop_ab_test(client):
    """POST /ab-tests/{test_id}/stop transitions running to completed."""
    running_test = _make_row({
        **{k: _ab_test_row[k] for k in _ab_test_row.keys()},
        "status": "running",
    })
    completed_row = _make_row({
        **{k: _ab_test_row[k] for k in _ab_test_row.keys()},
        "status": "completed",
        "completed_at": "2024-01-03T00:00:00",
    })
    conn = _make_async_conn()
    conn.fetchrow.side_effect = [running_test, completed_row]
    deps.db_pool = _make_pool(conn)
    deps.http_client = None  # no LiteLLM cleanup needed

    async with client:
        resp = await client.post("/api/v1/ab-tests/test-uuid-1/stop")

    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_stop_ab_test_not_running(client):
    """POST /ab-tests/{test_id}/stop returns 400 when test is not running."""
    # draft status test
    conn = _make_async_conn(fetchrow_return=_ab_test_row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post("/api/v1/ab-tests/test-uuid-1/stop")

    assert resp.status_code == 400
    assert "not running" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_promote_ab_test(client):
    """POST /ab-tests/{test_id}/promote records promotion snapshot and completes test."""
    running_test = _make_row({
        **{k: _ab_test_row[k] for k in _ab_test_row.keys()},
        "status": "running",
    })
    completed_row = _make_row({
        **{k: _ab_test_row[k] for k in _ab_test_row.keys()},
        "status": "completed",
        "completed_at": "2024-01-03T00:00:00",
    })
    conn = _make_async_conn()
    conn.fetchrow.side_effect = [running_test, completed_row]
    deps.db_pool = _make_pool(conn)
    deps.http_client = None  # no LiteLLM cleanup

    async with client:
        resp = await client.post("/api/v1/ab-tests/test-uuid-1/promote")

    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
    # Verify promotion snapshot was inserted
    assert conn.execute.call_count >= 1


@pytest.mark.asyncio
async def test_promote_not_running(client):
    """POST /ab-tests/{test_id}/promote returns 400 when test is not running."""
    conn = _make_async_conn(fetchrow_return=_ab_test_row)  # status=draft
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post("/api/v1/ab-tests/test-uuid-1/promote")

    assert resp.status_code == 400
    assert "not running" in resp.json()["detail"].lower()


# ============================================================================
# Snapshot Tests
# ============================================================================


@pytest.mark.asyncio
async def test_list_snapshots(client):
    """GET /ab-tests/{test_id}/snapshots returns snapshots for a test."""
    test_id_row = _make_row({"id": "test-uuid-1"})
    conn = _make_async_conn(fetch_return=[_snapshot_row])
    conn.fetchrow.return_value = test_id_row
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/ab-tests/test-uuid-1/snapshots")

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["recommendation"] == "promote"


@pytest.mark.asyncio
async def test_list_snapshots_test_not_found(client):
    """GET /ab-tests/{test_id}/snapshots returns 404 when test doesn't exist."""
    conn = _make_async_conn(fetchrow_return=None)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/ab-tests/nonexistent-uuid/snapshots")

    assert resp.status_code == 404


# ============================================================================
# _is_variant_better Helper Tests
# ============================================================================

from routers.ab_tests import _is_variant_better  # noqa: E402


def test_is_variant_better_promote():
    """_is_variant_better returns 'promote' when variant has lower latency (>5% improvement)."""
    base = {"avg_latency_ms": 300}
    variant = {"avg_latency_ms": 200}
    result = _is_variant_better(base, variant, "avg_latency_ms")
    assert result == "promote"


def test_is_variant_better_rollback():
    """_is_variant_better returns 'rollback' when variant is much worse (>10% degradation)."""
    base = {"avg_latency_ms": 200}
    variant = {"avg_latency_ms": 350}
    result = _is_variant_better(base, variant, "avg_latency_ms")
    assert result == "rollback"


def test_is_variant_better_continue():
    """_is_variant_better returns 'continue' when values are close or None."""
    # Close values
    base = {"avg_latency_ms": 300}
    variant = {"avg_latency_ms": 295}
    assert _is_variant_better(base, variant, "avg_latency_ms") == "continue"

    # None values
    base_none = {"avg_latency_ms": None}
    variant_none = {"avg_latency_ms": 300}
    assert _is_variant_better(base_none, variant_none, "avg_latency_ms") == "continue"

    # Both zero
    base_zero = {"avg_latency_ms": 0}
    variant_zero = {"avg_latency_ms": 0}
    assert _is_variant_better(base_zero, variant_zero, "avg_latency_ms") == "continue"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
