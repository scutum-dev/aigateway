"""Unit tests for the SLA router.

Tests SLA definitions CRUD, provider health metrics, violation management,
failover rules CRUD, and manual failover triggering.
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

_sla_def_row = _make_row(
    {
        "id": "sla-uuid-1",
        "name": "Production SLA",
        "provider": "openai",
        "model_pattern": "gpt-4*",
        "target_p50_ms": 500,
        "target_p95_ms": 2000,
        "target_p99_ms": 5000,
        "target_error_rate": 0.01,
        "target_availability": 0.999,
        "evaluation_window_minutes": 60,
        "alert_channels": ["slack", "email"],
        "is_active": True,
        "created_at": "2024-01-01T00:00:00",
    }
)

_health_row = _make_row(
    {
        "id": "h-uuid-1",
        "provider": "openai",
        "model": "gpt-4o",
        "bucket_start": "2024-01-01T00:00:00",
        "request_count": 100,
        "error_count": 2,
        "p50_latency_ms": 300,
        "p95_latency_ms": 1500,
        "p99_latency_ms": 3000,
        "avg_latency_ms": 500,
        "total_tokens": 50000,
        "total_cost": 5.0,
    }
)

_violation_row = _make_row(
    {
        "id": "v-uuid-1",
        "sla_definition_id": "sla-uuid-1",
        "provider": "openai",
        "model": "gpt-4o",
        "violation_type": "latency_p95",
        "threshold_value": 2000.0,
        "actual_value": 3000.0,
        "alert_sent": True,
        "resolved_at": None,
        "created_at": "2024-01-01T00:00:00",
    }
)

_failover_row = _make_row(
    {
        "id": "fo-uuid-1",
        "primary_model": "gpt-4o",
        "fallback_model": "gpt-4o-mini",
        "trigger_condition": "error_rate",
        "trigger_threshold": 0.05,
        "cooldown_minutes": 15,
        "is_active": True,
        "last_triggered_at": None,
        "created_at": "2024-01-01T00:00:00",
    }
)


# ============================================================================
# SLA Definitions CRUD
# ============================================================================


@pytest.mark.asyncio
async def test_list_definitions(client):
    """GET /sla/definitions returns all SLA definitions."""
    conn = _make_async_conn(fetch_return=[_sla_def_row])
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/sla/definitions")

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["name"] == "Production SLA"
    assert data[0]["provider"] == "openai"


@pytest.mark.asyncio
async def test_list_definitions_no_db(client):
    """GET /sla/definitions returns 503 when database is unavailable."""
    deps.db_pool = None

    async with client:
        resp = await client.get("/api/v1/sla/definitions")

    assert resp.status_code == 503
    assert "Database not available" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_definition(client):
    """POST /sla/definitions creates an SLA definition."""
    conn = _make_async_conn(fetchrow_return=_sla_def_row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post(
            "/api/v1/sla/definitions",
            json={
                "name": "Production SLA",
                "provider": "openai",
                "model_pattern": "gpt-4*",
                "target_p50_ms": 500,
                "target_p95_ms": 2000,
                "target_p99_ms": 5000,
                "target_error_rate": 0.01,
                "target_availability": 0.999,
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Production SLA"
    assert data["target_p95_ms"] == 2000
    conn.fetchrow.assert_called_once()


@pytest.mark.asyncio
async def test_update_definition(client):
    """PUT /sla/definitions/{id} updates the definition."""
    updated_row = _make_row(
        {
            **{k: _sla_def_row[k] for k in _sla_def_row.keys()},
            "name": "Updated SLA",
        }
    )
    conn = _make_async_conn(fetchrow_return=updated_row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.put(
            "/api/v1/sla/definitions/sla-uuid-1",
            json={
                "name": "Updated SLA",
            },
        )

    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated SLA"


@pytest.mark.asyncio
async def test_update_definition_not_found(client):
    """PUT /sla/definitions/{id} returns 404 for nonexistent definition."""
    conn = _make_async_conn(fetchrow_return=None)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.put(
            "/api/v1/sla/definitions/nonexistent",
            json={
                "name": "Updated SLA",
            },
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_definition(client):
    """DELETE /sla/definitions/{id} removes the definition."""
    conn = _make_async_conn(execute_return="DELETE 1")
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.delete("/api/v1/sla/definitions/sla-uuid-1")

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_delete_definition_not_found(client):
    """DELETE /sla/definitions/{id} returns 404 for nonexistent definition."""
    conn = _make_async_conn(execute_return="DELETE 0")
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.delete("/api/v1/sla/definitions/nonexistent")

    assert resp.status_code == 404


# ============================================================================
# Provider Health
# ============================================================================


@pytest.mark.asyncio
async def test_get_health(client):
    """GET /sla/health returns latest health metrics per provider/model."""
    conn = _make_async_conn(fetch_return=[_health_row])
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/sla/health")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["provider"] == "openai"
    assert data[0]["model"] == "gpt-4o"
    assert data[0]["request_count"] == 100


@pytest.mark.asyncio
async def test_get_health_history(client):
    """GET /sla/health/history returns historical metrics with filters."""
    conn = _make_async_conn(fetch_return=[_health_row])
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/sla/health/history?provider=openai&hours=48")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["provider"] == "openai"


# ============================================================================
# SLA Violations
# ============================================================================


@pytest.mark.asyncio
async def test_list_violations(client):
    """GET /sla/violations returns all violations."""
    conn = _make_async_conn(fetch_return=[_violation_row])
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/sla/violations")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["violation_type"] == "latency_p95"
    assert data[0]["actual_value"] == 3000.0


@pytest.mark.asyncio
async def test_list_violations_active(client):
    """GET /sla/violations/active returns only unresolved violations."""
    conn = _make_async_conn(fetch_return=[_violation_row])
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/sla/violations/active")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["resolved_at"] is None


@pytest.mark.asyncio
async def test_resolve_violation(client):
    """POST /sla/violations/{id}/resolve marks a violation as resolved."""
    conn = _make_async_conn(fetchrow_return=_violation_row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post("/api/v1/sla/violations/v-uuid-1/resolve")

    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"
    conn.execute.assert_called_once()


@pytest.mark.asyncio
async def test_resolve_violation_not_found(client):
    """POST /sla/violations/{id}/resolve returns 404 for nonexistent violation."""
    conn = _make_async_conn(fetchrow_return=None)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post("/api/v1/sla/violations/nonexistent/resolve")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_resolve_already_resolved(client):
    """POST /sla/violations/{id}/resolve returns 400 when already resolved."""
    resolved_row = _make_row(
        {
            **{k: _violation_row[k] for k in _violation_row.keys()},
            "resolved_at": "2024-01-02T00:00:00",
        }
    )
    conn = _make_async_conn(fetchrow_return=resolved_row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post("/api/v1/sla/violations/v-uuid-1/resolve")

    assert resp.status_code == 400
    assert "already resolved" in resp.json()["detail"].lower()


# ============================================================================
# Failover Rules
# ============================================================================


@pytest.mark.asyncio
async def test_list_failover_rules(client):
    """GET /sla/failover-rules returns all failover rules."""
    conn = _make_async_conn(fetch_return=[_failover_row])
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/sla/failover-rules")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["primary_model"] == "gpt-4o"
    assert data[0]["fallback_model"] == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_create_failover_rule(client):
    """POST /sla/failover-rules creates a failover rule."""
    conn = _make_async_conn(fetchrow_return=_failover_row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post(
            "/api/v1/sla/failover-rules",
            json={
                "primary_model": "gpt-4o",
                "fallback_model": "gpt-4o-mini",
                "trigger_condition": "error_rate",
                "trigger_threshold": 0.05,
                "cooldown_minutes": 15,
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["primary_model"] == "gpt-4o"
    assert data["trigger_threshold"] == 0.05
    conn.fetchrow.assert_called_once()


@pytest.mark.asyncio
async def test_update_failover_rule(client):
    """PUT /sla/failover-rules/{id} updates a failover rule."""
    updated_row = _make_row(
        {
            **{k: _failover_row[k] for k in _failover_row.keys()},
            "cooldown_minutes": 30,
        }
    )
    conn = _make_async_conn(fetchrow_return=updated_row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.put(
            "/api/v1/sla/failover-rules/fo-uuid-1",
            json={
                "primary_model": "gpt-4o",
                "fallback_model": "gpt-4o-mini",
                "cooldown_minutes": 30,
            },
        )

    assert resp.status_code == 200
    assert resp.json()["cooldown_minutes"] == 30


@pytest.mark.asyncio
async def test_delete_failover_rule(client):
    """DELETE /sla/failover-rules/{id} removes a failover rule."""
    conn = _make_async_conn(execute_return="DELETE 1")
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.delete("/api/v1/sla/failover-rules/fo-uuid-1")

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_trigger_failover(client):
    """POST /sla/failover-rules/{id}/trigger triggers an active failover rule."""
    conn = _make_async_conn(fetchrow_return=_failover_row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post("/api/v1/sla/failover-rules/fo-uuid-1/trigger")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "triggered"
    assert data["primary_model"] == "gpt-4o"
    assert data["fallback_model"] == "gpt-4o-mini"
    conn.execute.assert_called_once()


@pytest.mark.asyncio
async def test_trigger_inactive_failover(client):
    """POST /sla/failover-rules/{id}/trigger returns 400 for inactive rule."""
    inactive_rule = _make_row(
        {
            **{k: _failover_row[k] for k in _failover_row.keys()},
            "is_active": False,
        }
    )
    conn = _make_async_conn(fetchrow_return=inactive_rule)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post("/api/v1/sla/failover-rules/fo-uuid-1/trigger")

    assert resp.status_code == 400
    assert "inactive" in resp.json()["detail"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
