"""Unit tests for the DLP router (content detectors and scanning).

Tests the /api/v1/detectors and /api/v1/scan endpoints.
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

_detector_row = _make_row({
    "id": "det-1", "name": "Email PII", "description": "Detect emails",
    "detector_type": "pii", "config": '{"entity_types":["email"]}',
    "is_active": True, "created_at": "2024-01-01", "updated_at": None,
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
# List Detectors
# ============================================================================


class TestListDetectors:
    """Tests for GET /api/v1/detectors."""

    @pytest.mark.asyncio
    async def test_list_detectors(self, client):
        conn = _make_async_conn(fetch_return=[_detector_row])
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/detectors")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "det-1"
        assert data[0]["name"] == "Email PII"
        assert data[0]["detector_type"] == "pii"

    @pytest.mark.asyncio
    async def test_list_detectors_no_db(self, client):
        deps.db_pool = None

        async with client:
            resp = await client.get("/api/v1/detectors")

        assert resp.status_code == 503
        assert "Database not available" in resp.json()["detail"]


# ============================================================================
# Create Detector
# ============================================================================


class TestCreateDetector:
    """Tests for POST /api/v1/detectors."""

    @pytest.mark.asyncio
    async def test_create_detector(self, client):
        conn = _make_async_conn(fetchrow_return=_detector_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.post("/api/v1/detectors", json={
                "name": "Email PII",
                "description": "Detect emails",
                "detector_type": "pii",
                "config": {"entity_types": ["email"]},
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "det-1"
        assert data["name"] == "Email PII"
        conn.fetchrow.assert_called_once()


# ============================================================================
# Get Detector
# ============================================================================


class TestGetDetector:
    """Tests for GET /api/v1/detectors/{detector_id}."""

    @pytest.mark.asyncio
    async def test_get_detector(self, client):
        conn = _make_async_conn(fetchrow_return=_detector_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/detectors/det-1")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "det-1"
        assert data["detector_type"] == "pii"

    @pytest.mark.asyncio
    async def test_get_detector_not_found(self, client):
        conn = _make_async_conn(fetchrow_return=None)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/detectors/nonexistent")

        assert resp.status_code == 404
        assert "Detector not found" in resp.json()["detail"]


# ============================================================================
# Update Detector
# ============================================================================


class TestUpdateDetector:
    """Tests for PUT /api/v1/detectors/{detector_id}."""

    @pytest.mark.asyncio
    async def test_update_detector(self, client):
        updated_row = _make_row({
            "id": "det-1", "name": "Updated PII", "description": "Detect emails",
            "detector_type": "pii", "config": '{"entity_types":["email"]}',
            "is_active": True, "created_at": "2024-01-01", "updated_at": "2024-06-01",
        })
        conn = _make_async_conn(fetchrow_return=updated_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.put("/api/v1/detectors/det-1", json={
                "name": "Updated PII",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated PII"

    @pytest.mark.asyncio
    async def test_update_detector_not_found(self, client):
        conn = _make_async_conn(fetchrow_return=None)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.put("/api/v1/detectors/nonexistent", json={
                "name": "Updated",
            })

        assert resp.status_code == 404
        assert "Detector not found" in resp.json()["detail"]


# ============================================================================
# Delete Detector
# ============================================================================


class TestDeleteDetector:
    """Tests for DELETE /api/v1/detectors/{detector_id}."""

    @pytest.mark.asyncio
    async def test_delete_detector(self, client):
        conn = _make_async_conn(execute_return="DELETE 1")
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.delete("/api/v1/detectors/det-1")

        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    @pytest.mark.asyncio
    async def test_delete_detector_not_found(self, client):
        conn = _make_async_conn(execute_return="DELETE 0")
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.delete("/api/v1/detectors/nonexistent")

        assert resp.status_code == 404
        assert "Detector not found" in resp.json()["detail"]


# ============================================================================
# Test Detector
# ============================================================================


class TestDetectorTest:
    """Tests for POST /api/v1/detectors/{detector_id}/test."""

    @pytest.mark.asyncio
    async def test_test_detector(self, client):
        det_row = _make_row({
            "id": "det-1", "name": "Email PII", "description": "Detect emails",
            "detector_type": "pii", "config": '{"entity_types":["email"]}',
            "is_active": True, "created_at": "2024-01-01", "updated_at": None,
        })
        conn = _make_async_conn(fetchrow_return=det_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.post("/api/v1/detectors/det-1/test", json={
                "text": "Contact user@example.com for details.",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["matches"]) >= 1
        assert data["matches"][0]["label"] == "email"

    @pytest.mark.asyncio
    async def test_test_detector_not_found(self, client):
        conn = _make_async_conn(fetchrow_return=None)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.post("/api/v1/detectors/nonexistent/test", json={
                "text": "some text",
            })

        assert resp.status_code == 404
        assert "Detector not found" in resp.json()["detail"]


# ============================================================================
# Scan Text
# ============================================================================


class TestScanText:
    """Tests for POST /api/v1/scan."""

    @pytest.mark.asyncio
    async def test_scan_text(self, client):
        det_row = _make_row({
            "id": "det-1", "name": "Email PII", "description": "Detect emails",
            "detector_type": "pii", "config": '{"entity_types":["email"]}',
            "is_active": True, "created_at": "2024-01-01", "updated_at": None,
        })
        conn = _make_async_conn(fetch_return=[det_row])
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.post("/api/v1/scan", json={
                "text": "Email me at test@example.com",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["clean"] is False
        assert len(data["matches"]) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
