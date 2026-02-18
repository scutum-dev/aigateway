"""Integration tests for A/B test lifecycle workflows.

Tests the full A/B test lifecycle: create -> start -> collect metrics ->
stop/promote -> snapshots, with mocked DB and LiteLLM integration.
Also tests the _is_variant_better comparison logic.
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

# Import _is_variant_better for direct testing
from routers.ab_tests import _is_variant_better


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


def _mock_http_response(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    resp.raise_for_status = MagicMock()
    return resp


def _ab_test_row(overrides=None):
    """Return a base A/B test row dict."""
    base = {
        "id": "ab-001",
        "name": "GPT-4o vs Claude-3.5",
        "status": "draft",
        "base_model": "gpt-4o",
        "variant_model": "claude-3.5-sonnet",
        "traffic_split_percent": 10,
        "success_metric": "cost_efficiency",
        "promotion_threshold": None,
        "rollback_threshold": None,
        "auto_promote": False,
        "auto_rollback": True,
        "started_at": None,
        "completed_at": None,
        "created_by": "test-admin",
        "created_at": "2026-01-01T00:00:00",
    }
    if overrides:
        base.update(overrides)
    return base


def _snapshot_row(overrides=None):
    """Return a base snapshot row dict."""
    base = {
        "id": "snap-001",
        "test_id": "ab-001",
        "snapshot_at": "2026-01-15T00:00:00",
        "base_metrics": json.dumps({"avg_latency_ms": 200, "avg_cost": 0.003}),
        "variant_metrics": json.dumps({"avg_latency_ms": 150, "avg_cost": 0.002}),
        "recommendation": "continue",
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
# 1. Create draft A/B test
# ============================================================================


@pytest.mark.asyncio
async def test_create_draft_ab_test(client):
    """POST /ab-tests creates a test in draft status."""
    row = _make_row(_ab_test_row())
    conn = _make_async_conn(fetchrow_return=row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post("/api/v1/ab-tests", json={
            "name": "GPT-4o vs Claude-3.5",
            "base_model": "gpt-4o",
            "variant_model": "claude-3.5-sonnet",
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "draft"
    assert data["base_model"] == "gpt-4o"
    assert data["variant_model"] == "claude-3.5-sonnet"


# ============================================================================
# 2. Start test changes status
# ============================================================================


@pytest.mark.asyncio
async def test_start_test_changes_status(client):
    """POST /ab-tests/{id}/start changes status from draft to running."""
    draft_row = _make_row(_ab_test_row({"status": "draft"}))
    running_row = _make_row(_ab_test_row({"status": "running", "started_at": "2026-01-15T00:00:00"}))

    conn = _make_async_conn()
    conn.fetchrow = AsyncMock(side_effect=[draft_row, running_row])
    deps.db_pool = _make_pool(conn)
    # Mock LiteLLM http_client for _add_variant_to_litellm
    deps.http_client = AsyncMock()
    deps.http_client.post = AsyncMock(return_value=_mock_http_response(200, {"model_info": {"id": "m-variant"}}))

    async with client:
        resp = await client.post("/api/v1/ab-tests/ab-001/start")

    assert resp.status_code == 200
    assert resp.json()["status"] == "running"


# ============================================================================
# 3. Start adds variant to LiteLLM
# ============================================================================


@pytest.mark.asyncio
async def test_start_adds_variant_to_litellm(client):
    """POST /ab-tests/{id}/start calls LiteLLM /model/new."""
    draft_row = _make_row(_ab_test_row({"status": "draft"}))
    running_row = _make_row(_ab_test_row({"status": "running"}))

    conn = _make_async_conn()
    conn.fetchrow = AsyncMock(side_effect=[draft_row, running_row])
    deps.db_pool = _make_pool(conn)

    mock_litellm_resp = _mock_http_response(200, {"model_info": {"id": "variant-model-id"}})
    deps.http_client = AsyncMock()
    deps.http_client.post = AsyncMock(return_value=mock_litellm_resp)

    async with client:
        resp = await client.post("/api/v1/ab-tests/ab-001/start")

    assert resp.status_code == 200
    # Verify LiteLLM was called with /model/new
    post_calls = deps.http_client.post.call_args_list
    assert any("/model/new" in str(call) for call in post_calls)


# ============================================================================
# 4. Stop test removes variant
# ============================================================================


@pytest.mark.asyncio
async def test_stop_test_removes_variant(client):
    """POST /ab-tests/{id}/stop changes to completed and calls LiteLLM to remove variant."""
    running_row = _make_row(_ab_test_row({"status": "running"}))
    completed_row = _make_row(_ab_test_row({"status": "completed", "completed_at": "2026-01-20T00:00:00"}))

    conn = _make_async_conn()
    conn.fetchrow = AsyncMock(side_effect=[running_row, completed_row])
    deps.db_pool = _make_pool(conn)

    # Mock LiteLLM for _remove_variant_from_litellm
    mock_list_resp = _mock_http_response(200, {"data": []})
    deps.http_client = AsyncMock()
    deps.http_client.get = AsyncMock(return_value=mock_list_resp)

    async with client:
        resp = await client.post("/api/v1/ab-tests/ab-001/stop")

    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


# ============================================================================
# 5. Promote records snapshot
# ============================================================================


@pytest.mark.asyncio
async def test_promote_records_snapshot(client):
    """POST /ab-tests/{id}/promote inserts a snapshot with 'promoted' recommendation."""
    running_row = _make_row(_ab_test_row({"status": "running"}))
    completed_row = _make_row(_ab_test_row({"status": "completed"}))

    conn = _make_async_conn()
    conn.fetchrow = AsyncMock(side_effect=[running_row, completed_row])
    conn.execute = AsyncMock()
    deps.db_pool = _make_pool(conn)

    mock_list_resp = _mock_http_response(200, {"data": []})
    deps.http_client = AsyncMock()
    deps.http_client.get = AsyncMock(return_value=mock_list_resp)

    async with client:
        resp = await client.post("/api/v1/ab-tests/ab-001/promote")

    assert resp.status_code == 200
    # Verify that execute was called with 'promoted' in the args
    execute_calls = conn.execute.call_args_list
    promoted_calls = [c for c in execute_calls if any("promoted" in str(arg) for arg in c[0])]
    assert len(promoted_calls) > 0


# ============================================================================
# 6. Cannot start running test
# ============================================================================


@pytest.mark.asyncio
async def test_cannot_start_running_test(client):
    """POST /ab-tests/{id}/start returns 400 if test is already running."""
    running_row = _make_row(_ab_test_row({"status": "running"}))
    conn = _make_async_conn(fetchrow_return=running_row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post("/api/v1/ab-tests/ab-001/start")

    assert resp.status_code == 400
    assert "Cannot start" in resp.json()["detail"]


# ============================================================================
# 7. Cannot stop draft test
# ============================================================================


@pytest.mark.asyncio
async def test_cannot_stop_draft_test(client):
    """POST /ab-tests/{id}/stop returns 400 if test is in draft status."""
    draft_row = _make_row(_ab_test_row({"status": "draft"}))
    conn = _make_async_conn(fetchrow_return=draft_row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post("/api/v1/ab-tests/ab-001/stop")

    assert resp.status_code == 400
    assert "not running" in resp.json()["detail"]


# ============================================================================
# 8. Cannot promote stopped test
# ============================================================================


@pytest.mark.asyncio
async def test_cannot_promote_stopped_test(client):
    """POST /ab-tests/{id}/promote returns 400 if test is completed."""
    completed_row = _make_row(_ab_test_row({"status": "completed"}))
    conn = _make_async_conn(fetchrow_return=completed_row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post("/api/v1/ab-tests/ab-001/promote")

    assert resp.status_code == 400
    assert "not running" in resp.json()["detail"]


# ============================================================================
# 9. _is_variant_better: lower latency promotes
# ============================================================================


def test_is_variant_better_lower_latency_promotes():
    """Variant with significantly lower avg_latency_ms returns 'promote'."""
    base = {"avg_latency_ms": 200}
    variant = {"avg_latency_ms": 150}  # 25% improvement (lower is better)
    result = _is_variant_better(base, variant, "avg_latency_ms")
    assert result == "promote"


# ============================================================================
# 10. _is_variant_better: much worse rollbacks
# ============================================================================


def test_is_variant_better_much_worse_rollbacks():
    """Variant with much worse metrics returns 'rollback'."""
    base = {"avg_latency_ms": 100}
    variant = {"avg_latency_ms": 150}  # 50% worse (lower is better)
    result = _is_variant_better(base, variant, "avg_latency_ms")
    assert result == "rollback"


# ============================================================================
# 11. _is_variant_better: similar continues
# ============================================================================


def test_is_variant_better_similar_continues():
    """Variant with similar metrics returns 'continue'."""
    base = {"avg_latency_ms": 100}
    variant = {"avg_latency_ms": 98}  # 2% improvement, within threshold
    result = _is_variant_better(base, variant, "avg_latency_ms")
    assert result == "continue"


# ============================================================================
# 12. _is_variant_better: null values continues
# ============================================================================


def test_is_variant_better_null_values_continues():
    """Missing metric values return 'continue'."""
    base = {"avg_latency_ms": None}
    variant = {"avg_latency_ms": 100}
    result = _is_variant_better(base, variant, "avg_latency_ms")
    assert result == "continue"

    # Also test with missing key
    result2 = _is_variant_better({}, {"avg_latency_ms": 100}, "avg_latency_ms")
    assert result2 == "continue"


# ============================================================================
# 13. List snapshots for test
# ============================================================================


@pytest.mark.asyncio
async def test_list_snapshots_for_test(client):
    """GET /ab-tests/{id}/snapshots returns all snapshots."""
    test_row = _make_row({"id": "ab-001"})
    snap1 = _make_row(_snapshot_row({"id": "snap-1", "recommendation": "continue"}))
    snap2 = _make_row(_snapshot_row({"id": "snap-2", "recommendation": "promote"}))

    conn = _make_async_conn()
    conn.fetchrow = AsyncMock(return_value=test_row)
    conn.fetch = AsyncMock(return_value=[snap1, snap2])
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/ab-tests/ab-001/snapshots")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["recommendation"] == "continue"
    assert data[1]["recommendation"] == "promote"


# ============================================================================
# 14. Get A/B test with snapshot
# ============================================================================


@pytest.mark.asyncio
async def test_get_ab_test_with_snapshot(client):
    """GET /ab-tests/{id} includes the latest snapshot."""
    test_row = _make_row(_ab_test_row({"status": "running"}))
    snapshot = _make_row(_snapshot_row({"recommendation": "promote"}))

    conn = _make_async_conn()
    conn.fetchrow = AsyncMock(side_effect=[test_row, snapshot])
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/ab-tests/ab-001")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running"
    assert data["latest_snapshot"] is not None
    assert data["latest_snapshot"]["recommendation"] == "promote"


# ============================================================================
# 15. Delete A/B test
# ============================================================================


@pytest.mark.asyncio
async def test_delete_ab_test(client):
    """DELETE /ab-tests/{id} returns success."""
    conn = _make_async_conn(execute_return="DELETE 1")
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.delete("/api/v1/ab-tests/ab-001")

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
