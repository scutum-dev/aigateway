"""Unit tests for the Organizations router (DB CRUD).

Tests the /api/v1/organizations endpoints including org CRUD,
business unit CRUD, team hierarchy, and membership management.
"""

import importlib.util
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

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

import deps
from auth import UserInfo, get_current_user, require_admin


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

_org_row = _make_row({
    "id": "org-uuid-1", "name": "Acme Corp", "slug": "acme", "description": "Test org",
    "max_budget": 1000.0, "allowed_models": ["gpt-4o"], "metadata": "{}",
    "is_active": True, "created_at": "2024-01-01T00:00:00", "updated_at": None,
    "bu_count": 2, "team_count": 5, "member_count": 10,
})

_bu_row = _make_row({
    "id": "bu-uuid-1", "org_id": "org-uuid-1", "name": "Engineering", "slug": "eng",
    "description": "Engineering BU", "max_budget": 500.0, "allowed_models": None,
    "is_active": True, "created_at": "2024-01-01T00:00:00", "updated_at": None,
})

_team_row = _make_row({
    "team_id": "team-1", "org_id": "org-uuid-1", "bu_id": "bu-uuid-1",
    "max_budget_override": 200.0, "created_at": "2024-01-01T00:00:00", "updated_at": None,
})

_member_row = _make_row({
    "id": "mem-uuid-1", "user_id": "user-1", "email": "user@test.com",
    "display_name": "Test User", "org_id": "org-uuid-1", "role": "member",
    "bu_id": None, "created_at": "2024-01-01T00:00:00",
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
# Organization CRUD
# ============================================================================


class TestListOrganizations:
    """Tests for GET /api/v1/organizations."""

    @pytest.mark.asyncio
    async def test_list_organizations(self, client):
        """GET /organizations returns list from DB."""
        conn = _make_async_conn(fetch_return=[_org_row])
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/organizations")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Acme Corp"
        assert data[0]["slug"] == "acme"
        assert data[0]["bu_count"] == 2
        assert data[0]["team_count"] == 5
        assert data[0]["member_count"] == 10

    @pytest.mark.asyncio
    async def test_list_organizations_no_db(self, client):
        """GET /organizations returns 503 when DB is unavailable."""
        deps.db_pool = None

        async with client:
            resp = await client.get("/api/v1/organizations")

        assert resp.status_code == 503
        assert "Database not available" in resp.json()["detail"]


class TestCreateOrganization:
    """Tests for POST /api/v1/organizations."""

    @pytest.mark.asyncio
    async def test_create_organization(self, client):
        """POST /organizations creates org and returns it."""
        conn = _make_async_conn(fetchrow_return=_org_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.post("/api/v1/organizations", json={
                "name": "Acme Corp",
                "slug": "acme",
                "description": "Test org",
                "max_budget": 1000.0,
                "allowed_models": ["gpt-4o"],
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Acme Corp"
        assert data["id"] == "org-uuid-1"
        conn.fetchrow.assert_called_once()


class TestGetOrganization:
    """Tests for GET /api/v1/organizations/{org_id}."""

    @pytest.mark.asyncio
    async def test_get_organization_found(self, client):
        """GET /organizations/{id} returns org when found."""
        conn = _make_async_conn(fetchrow_return=_org_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/organizations/org-uuid-1")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "org-uuid-1"
        assert data["name"] == "Acme Corp"

    @pytest.mark.asyncio
    async def test_get_organization_not_found(self, client):
        """GET /organizations/{id} returns 404 when not found."""
        conn = _make_async_conn(fetchrow_return=None)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/organizations/nonexistent")

        assert resp.status_code == 404
        assert "Organization not found" in resp.json()["detail"]


class TestUpdateOrganization:
    """Tests for PUT /api/v1/organizations/{org_id}."""

    @pytest.mark.asyncio
    async def test_update_organization(self, client):
        """PUT /organizations/{id} updates and returns org."""
        updated_row = _make_row({
            "id": "org-uuid-1", "name": "Acme Updated", "slug": "acme", "description": "Updated",
            "max_budget": 2000.0, "allowed_models": ["gpt-4o"], "metadata": "{}",
            "is_active": True, "created_at": "2024-01-01T00:00:00", "updated_at": "2024-01-02T00:00:00",
            "bu_count": 0, "team_count": 0, "member_count": 0,
        })
        conn = _make_async_conn(fetchrow_return=updated_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.put("/api/v1/organizations/org-uuid-1", json={
                "name": "Acme Updated",
                "max_budget": 2000.0,
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Acme Updated"
        assert data["max_budget"] == 2000.0

    @pytest.mark.asyncio
    async def test_update_organization_no_fields(self, client):
        """PUT /organizations/{id} returns 400 when no fields provided."""
        conn = _make_async_conn()
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.put("/api/v1/organizations/org-uuid-1", json={})

        assert resp.status_code == 400
        assert "No fields to update" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_organization_not_found(self, client):
        """PUT /organizations/{id} returns 404 when org not found."""
        conn = _make_async_conn(fetchrow_return=None)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.put("/api/v1/organizations/nonexistent", json={
                "name": "Updated",
            })

        assert resp.status_code == 404
        assert "Organization not found" in resp.json()["detail"]


class TestDeleteOrganization:
    """Tests for DELETE /api/v1/organizations/{org_id}."""

    @pytest.mark.asyncio
    async def test_delete_organization(self, client):
        """DELETE /organizations/{id} deletes org."""
        conn = _make_async_conn(execute_return="DELETE 1")
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.delete("/api/v1/organizations/org-uuid-1")

        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    @pytest.mark.asyncio
    async def test_delete_organization_not_found(self, client):
        """DELETE /organizations/{id} returns 404 when not found."""
        conn = _make_async_conn(execute_return="DELETE 0")
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.delete("/api/v1/organizations/nonexistent")

        assert resp.status_code == 404
        assert "Organization not found" in resp.json()["detail"]


# ============================================================================
# Business Unit CRUD
# ============================================================================


class TestBusinessUnits:
    """Tests for /api/v1/organizations/{org_id}/business-units endpoints."""

    @pytest.mark.asyncio
    async def test_list_business_units(self, client):
        """GET /organizations/{id}/business-units returns list."""
        conn = _make_async_conn(fetch_return=[_bu_row])
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/organizations/org-uuid-1/business-units")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Engineering"
        assert data[0]["org_id"] == "org-uuid-1"

    @pytest.mark.asyncio
    async def test_create_business_unit(self, client):
        """POST /organizations/{id}/business-units creates BU."""
        conn = _make_async_conn(fetchrow_return=_bu_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.post("/api/v1/organizations/org-uuid-1/business-units", json={
                "name": "Engineering",
                "slug": "eng",
                "description": "Engineering BU",
                "max_budget": 500.0,
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Engineering"
        assert data["id"] == "bu-uuid-1"
        conn.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_business_unit(self, client):
        """PUT /organizations/{id}/business-units/{bu_id} updates BU."""
        updated_bu = _make_row({
            "id": "bu-uuid-1", "org_id": "org-uuid-1", "name": "Eng Updated", "slug": "eng",
            "description": "Updated BU", "max_budget": 700.0, "allowed_models": None,
            "is_active": True, "created_at": "2024-01-01T00:00:00", "updated_at": "2024-01-02T00:00:00",
        })
        conn = _make_async_conn(fetchrow_return=updated_bu)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.put(
                "/api/v1/organizations/org-uuid-1/business-units/bu-uuid-1",
                json={"name": "Eng Updated", "max_budget": 700.0},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Eng Updated"
        assert data["max_budget"] == 700.0

    @pytest.mark.asyncio
    async def test_update_business_unit_not_found(self, client):
        """PUT /organizations/{id}/business-units/{bu_id} returns 404."""
        conn = _make_async_conn(fetchrow_return=None)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.put(
                "/api/v1/organizations/org-uuid-1/business-units/nonexistent",
                json={"name": "Updated"},
            )

        assert resp.status_code == 404
        assert "Business unit not found" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_delete_business_unit(self, client):
        """DELETE /organizations/{id}/business-units/{bu_id} deletes BU."""
        conn = _make_async_conn(execute_return="DELETE 1")
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.delete(
                "/api/v1/organizations/org-uuid-1/business-units/bu-uuid-1"
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    @pytest.mark.asyncio
    async def test_delete_business_unit_not_found(self, client):
        """DELETE /organizations/{id}/business-units/{bu_id} returns 404."""
        conn = _make_async_conn(execute_return="DELETE 0")
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.delete(
                "/api/v1/organizations/org-uuid-1/business-units/nonexistent"
            )

        assert resp.status_code == 404
        assert "Business unit not found" in resp.json()["detail"]


# ============================================================================
# Team Hierarchy
# ============================================================================


class TestTeamHierarchy:
    """Tests for /api/v1/organizations/{org_id}/teams endpoints."""

    @pytest.mark.asyncio
    async def test_assign_team_to_org(self, client):
        """POST /organizations/{id}/teams/{team_id} assigns team."""
        conn = _make_async_conn(execute_return="INSERT 0 1")
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.post(
                "/api/v1/organizations/org-uuid-1/teams/team-1",
                json={"bu_id": "bu-uuid-1", "max_budget_override": 200.0},
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "assigned"
        # execute called for the INSERT + audit log_audit_event
        assert conn.execute.call_count >= 1
        first_call_sql = conn.execute.call_args_list[0][0][0]
        assert "team_hierarchy" in first_call_sql

    @pytest.mark.asyncio
    async def test_remove_team_from_org(self, client):
        """DELETE /organizations/{id}/teams/{team_id} removes team."""
        conn = _make_async_conn(execute_return="DELETE 1")
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.delete(
                "/api/v1/organizations/org-uuid-1/teams/team-1"
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "removed"

    @pytest.mark.asyncio
    async def test_remove_team_not_found(self, client):
        """DELETE /organizations/{id}/teams/{team_id} returns 404."""
        conn = _make_async_conn(execute_return="DELETE 0")
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.delete(
                "/api/v1/organizations/org-uuid-1/teams/nonexistent"
            )

        assert resp.status_code == 404
        assert "Team assignment not found" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_org_teams(self, client):
        """GET /organizations/{id}/teams returns team list."""
        conn = _make_async_conn(fetch_return=[_team_row])
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/organizations/org-uuid-1/teams")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["team_id"] == "team-1"
        assert data[0]["org_id"] == "org-uuid-1"
        assert data[0]["bu_id"] == "bu-uuid-1"
        assert data[0]["max_budget_override"] == 200.0


# ============================================================================
# Memberships
# ============================================================================


class TestOrgMemberships:
    """Tests for /api/v1/organizations/{org_id}/members endpoints."""

    @pytest.mark.asyncio
    async def test_list_org_members(self, client):
        """GET /organizations/{id}/members returns member list."""
        conn = _make_async_conn(fetch_return=[_member_row])
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/organizations/org-uuid-1/members")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["user_id"] == "user-1"
        assert data[0]["email"] == "user@test.com"
        assert data[0]["display_name"] == "Test User"
        assert data[0]["role"] == "member"

    @pytest.mark.asyncio
    async def test_add_org_member(self, client):
        """POST /organizations/{id}/members adds member."""
        conn = _make_async_conn(fetchrow_return=_member_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.post("/api/v1/organizations/org-uuid-1/members", json={
                "user_id": "user-1",
                "role": "member",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "user-1"
        assert data["org_id"] == "org-uuid-1"
        assert data["role"] == "member"
        conn.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_org_member(self, client):
        """PUT /organizations/{id}/members/{user_id} updates role."""
        conn = _make_async_conn(execute_return="UPDATE 1")
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.put(
                "/api/v1/organizations/org-uuid-1/members/user-1",
                json={"role": "admin"},
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"

    @pytest.mark.asyncio
    async def test_update_org_member_not_found(self, client):
        """PUT /organizations/{id}/members/{user_id} returns 404."""
        conn = _make_async_conn(execute_return="UPDATE 0")
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.put(
                "/api/v1/organizations/org-uuid-1/members/nonexistent",
                json={"role": "admin"},
            )

        assert resp.status_code == 404
        assert "Membership not found" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_remove_org_member(self, client):
        """DELETE /organizations/{id}/members/{user_id} removes member."""
        conn = _make_async_conn(execute_return="DELETE 1")
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.delete(
                "/api/v1/organizations/org-uuid-1/members/user-1"
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "removed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
