"""Unit tests for the Chargeback router.

Tests cost allocation rules CRUD, chargeback report listing and retrieval,
report finalization, CSV export, and budget forecast listing.
"""

import importlib.util
import json
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

_rule_row = _make_row({
    "id": "rule-uuid-1", "name": "Engineering", "team_id": "team-1",
    "allocation_type": "team", "allocation_target": "eng-dept",
    "allocation_percent": 100.0, "metadata": "{}", "is_active": True,
    "created_at": "2024-01-01T00:00:00",
})

_report_row = _make_row({
    "id": "rpt-uuid-1", "report_period": "2026-01", "status": "draft",
    "total_cost": 1500.50, "breakdown": '[]', "generated_by": "admin",
    "finalized_at": None, "created_at": "2024-01-01T00:00:00",
})

_forecast_row = _make_row({
    "id": "fc-uuid-1", "team_id": "team-1", "forecast_period": "2026-03",
    "forecast_type": "weighted_moving_avg", "forecasted_cost": 1200.0,
    "confidence_low": 720.0, "confidence_high": 1680.0,
    "actual_cost": None, "created_at": "2024-01-01T00:00:00",
})


# ============================================================================
# Cost Allocation Rules CRUD
# ============================================================================


@pytest.mark.asyncio
async def test_list_rules(client):
    """GET /cost-allocation/rules returns all allocation rules."""
    conn = _make_async_conn(fetch_return=[_rule_row])
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/cost-allocation/rules")

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["name"] == "Engineering"
    assert data[0]["allocation_type"] == "team"


@pytest.mark.asyncio
async def test_list_rules_no_db(client):
    """GET /cost-allocation/rules returns 503 when database is unavailable."""
    deps.db_pool = None

    async with client:
        resp = await client.get("/api/v1/cost-allocation/rules")

    assert resp.status_code == 503
    assert "Database not available" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_rule(client):
    """POST /cost-allocation/rules creates a new allocation rule."""
    conn = _make_async_conn(fetchrow_return=_rule_row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post("/api/v1/cost-allocation/rules", json={
            "name": "Engineering",
            "team_id": "team-1",
            "allocation_type": "team",
            "allocation_target": "eng-dept",
            "allocation_percent": 100.0,
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Engineering"
    assert data["allocation_target"] == "eng-dept"
    conn.fetchrow.assert_called_once()


@pytest.mark.asyncio
async def test_update_rule(client):
    """PUT /cost-allocation/rules/{id} updates an allocation rule."""
    updated_row = _make_row({
        **{k: _rule_row[k] for k in _rule_row.keys()},
        "allocation_percent": 75.0,
    })
    conn = _make_async_conn(fetchrow_return=updated_row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.put("/api/v1/cost-allocation/rules/rule-uuid-1", json={
            "name": "Engineering",
            "allocation_type": "team",
            "allocation_target": "eng-dept",
            "allocation_percent": 75.0,
        })

    assert resp.status_code == 200
    assert resp.json()["allocation_percent"] == 75.0


@pytest.mark.asyncio
async def test_update_rule_not_found(client):
    """PUT /cost-allocation/rules/{id} returns 404 for nonexistent rule."""
    conn = _make_async_conn(fetchrow_return=None)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.put("/api/v1/cost-allocation/rules/nonexistent", json={
            "name": "Test",
            "allocation_type": "team",
            "allocation_target": "dept",
        })

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_rule(client):
    """DELETE /cost-allocation/rules/{id} removes an allocation rule."""
    conn = _make_async_conn(execute_return="DELETE 1")
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.delete("/api/v1/cost-allocation/rules/rule-uuid-1")

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_delete_rule_not_found(client):
    """DELETE /cost-allocation/rules/{id} returns 404 for nonexistent rule."""
    conn = _make_async_conn(execute_return="DELETE 0")
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.delete("/api/v1/cost-allocation/rules/nonexistent")

    assert resp.status_code == 404


# ============================================================================
# Chargeback Reports
# ============================================================================


@pytest.mark.asyncio
async def test_list_reports(client):
    """GET /chargeback/reports returns all reports."""
    conn = _make_async_conn(fetch_return=[_report_row])
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/chargeback/reports")

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["report_period"] == "2026-01"
    assert data[0]["status"] == "draft"


@pytest.mark.asyncio
async def test_get_report(client):
    """GET /chargeback/reports/{id} returns a specific report."""
    conn = _make_async_conn(fetchrow_return=_report_row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/chargeback/reports/rpt-uuid-1")

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "rpt-uuid-1"
    assert data["total_cost"] == 1500.50


@pytest.mark.asyncio
async def test_get_report_not_found(client):
    """GET /chargeback/reports/{id} returns 404 for nonexistent report."""
    conn = _make_async_conn(fetchrow_return=None)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/chargeback/reports/nonexistent")

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_finalize_report(client):
    """POST /chargeback/reports/{id}/finalize locks a draft report."""
    conn = _make_async_conn(fetchrow_return=_report_row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post("/api/v1/chargeback/reports/rpt-uuid-1/finalize")

    assert resp.status_code == 200
    assert resp.json()["status"] == "finalized"
    conn.execute.assert_called_once()


@pytest.mark.asyncio
async def test_finalize_already_finalized(client):
    """POST /chargeback/reports/{id}/finalize returns 400 for already finalized report."""
    finalized_row = _make_row({
        **{k: _report_row[k] for k in _report_row.keys()},
        "status": "finalized",
        "finalized_at": "2024-01-02T00:00:00",
    })
    conn = _make_async_conn(fetchrow_return=finalized_row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post("/api/v1/chargeback/reports/rpt-uuid-1/finalize")

    assert resp.status_code == 400
    assert "already finalized" in resp.json()["detail"].lower()


# ============================================================================
# Budget Forecasts
# ============================================================================


@pytest.mark.asyncio
async def test_list_forecasts(client):
    """GET /reports/forecast returns all budget forecasts."""
    conn = _make_async_conn(fetch_return=[_forecast_row])
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/reports/forecast")

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["forecast_period"] == "2026-03"
    assert data[0]["forecasted_cost"] == 1200.0
    assert data[0]["confidence_low"] == 720.0
    assert data[0]["confidence_high"] == 1680.0


# ============================================================================
# Export
# ============================================================================


@pytest.mark.asyncio
async def test_export_report_csv(client):
    """GET /chargeback/reports/{id}/export returns CSV content."""
    report_with_breakdown = _make_row({
        **{k: _report_row[k] for k in _report_row.keys()},
        "breakdown": json.dumps([{
            "team_id": "team-1",
            "allocation_target": "eng-dept",
            "allocation_type": "team",
            "original_cost": 1500.50,
            "allocated_cost": 1500.50,
            "allocation_percent": 100.0,
            "request_count": 200,
            "total_tokens": 50000,
        }]),
    })
    conn = _make_async_conn(fetchrow_return=report_with_breakdown)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/chargeback/reports/rpt-uuid-1/export?format=csv")

    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")
    body = resp.text
    assert "team_id" in body
    assert "team-1" in body
    assert "eng-dept" in body


@pytest.mark.asyncio
async def test_export_report_not_found(client):
    """GET /chargeback/reports/{id}/export returns 404 for nonexistent report."""
    conn = _make_async_conn(fetchrow_return=None)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/chargeback/reports/nonexistent/export")

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
