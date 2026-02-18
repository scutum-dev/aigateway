"""Unit tests for the SSO router (SSO configuration management).

Tests the /api/v1/organizations/{org_id}/sso endpoints.
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

_sso_row = _make_row({
    "id": "sso-1", "org_id": "org-1", "provider_type": "oidc",
    "provider_name": "Okta", "client_id": "my-client-id",
    "client_secret_encrypted": "encrypted-secret", "issuer_url": "https://dev.okta.com",
    "authorization_url": None, "token_url": None, "userinfo_url": None,
    "jwks_uri": None, "saml_metadata_url": None, "scopes": "openid email profile",
    "group_claim": "groups", "group_to_org_mapping": "{}",
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
# Get SSO Config
# ============================================================================


class TestGetSSO:
    """Tests for GET /api/v1/organizations/{org_id}/sso."""

    @pytest.mark.asyncio
    async def test_get_sso(self, client):
        conn = _make_async_conn(fetchrow_return=_sso_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/organizations/org-1/sso")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "sso-1"
        assert data["org_id"] == "org-1"
        assert data["provider_type"] == "oidc"
        assert data["provider_name"] == "Okta"

    @pytest.mark.asyncio
    async def test_get_sso_not_found(self, client):
        conn = _make_async_conn(fetchrow_return=None)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/organizations/org-999/sso")

        assert resp.status_code == 404
        assert "SSO config not found" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_sso_no_db(self, client):
        deps.db_pool = None

        async with client:
            resp = await client.get("/api/v1/organizations/org-1/sso")

        assert resp.status_code == 503
        assert "Database not available" in resp.json()["detail"]


# ============================================================================
# Create SSO Config
# ============================================================================


class TestCreateSSO:
    """Tests for POST /api/v1/organizations/{org_id}/sso."""

    @pytest.mark.asyncio
    async def test_create_sso(self, client):
        conn = _make_async_conn(fetchrow_return=_sso_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.post("/api/v1/organizations/org-1/sso", json={
                "provider_type": "oidc",
                "provider_name": "Okta",
                "client_id": "my-client-id",
                "client_secret": "my-secret",
                "issuer_url": "https://dev.okta.com",
                "scopes": "openid email profile",
                "group_claim": "groups",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "sso-1"
        assert data["provider_type"] == "oidc"
        assert data["provider_name"] == "Okta"

    @pytest.mark.asyncio
    async def test_create_sso_no_db(self, client):
        deps.db_pool = None

        async with client:
            resp = await client.post("/api/v1/organizations/org-1/sso", json={
                "provider_type": "oidc",
                "provider_name": "Okta",
            })

        assert resp.status_code == 503
        assert "Database not available" in resp.json()["detail"]


# ============================================================================
# Disable SSO
# ============================================================================


class TestDisableSSO:
    """Tests for DELETE /api/v1/organizations/{org_id}/sso."""

    @pytest.mark.asyncio
    async def test_disable_sso(self, client):
        conn = _make_async_conn(execute_return="UPDATE 1")
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.delete("/api/v1/organizations/org-1/sso")

        assert resp.status_code == 200
        assert resp.json()["status"] == "disabled"

    @pytest.mark.asyncio
    async def test_disable_sso_not_found(self, client):
        conn = _make_async_conn(execute_return="UPDATE 0")
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.delete("/api/v1/organizations/org-999/sso")

        assert resp.status_code == 404
        assert "SSO config not found" in resp.json()["detail"]


# ============================================================================
# Test SSO Connection
# ============================================================================


class TestSSOConnection:
    """Tests for POST /api/v1/organizations/{org_id}/sso/test."""

    @pytest.mark.asyncio
    async def test_sso_incomplete(self, client):
        """SSO config missing issuer_url or client_id returns error status."""
        incomplete_row = _make_row({
            "id": "sso-1", "org_id": "org-1", "provider_type": "oidc",
            "provider_name": "Okta", "client_id": None,
            "client_secret_encrypted": None, "issuer_url": None,
            "authorization_url": None, "token_url": None, "userinfo_url": None,
            "jwks_uri": None, "saml_metadata_url": None, "scopes": "openid",
            "group_claim": "groups", "group_to_org_mapping": "{}",
            "is_active": True, "created_at": "2024-01-01", "updated_at": None,
        })
        conn = _make_async_conn(fetchrow_return=incomplete_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.post("/api/v1/organizations/org-1/sso/test")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"
        assert "incomplete" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_sso_success(self, client):
        """SSO test with valid config and working discovery returns ok status."""
        conn = _make_async_conn(fetchrow_return=_sso_row)
        deps.db_pool = _make_pool(conn)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "issuer": "https://dev.okta.com",
            "authorization_endpoint": "https://dev.okta.com/authorize",
            "token_endpoint": "https://dev.okta.com/token",
            "userinfo_endpoint": "https://dev.okta.com/userinfo",
            "scopes_supported": ["openid", "email", "profile"],
        }

        http_client = AsyncMock()
        http_client.get.return_value = mock_response
        deps.http_client = http_client

        async with client:
            resp = await client.post("/api/v1/organizations/org-1/sso/test")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "working" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_sso_not_found(self, client):
        """SSO test for non-existent org returns 404."""
        conn = _make_async_conn(fetchrow_return=None)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.post("/api/v1/organizations/org-999/sso/test")

        assert resp.status_code == 404
        assert "SSO config not found" in resp.json()["detail"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
