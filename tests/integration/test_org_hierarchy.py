"""Integration tests for organization hierarchy workflows.

Tests multi-step organization CRUD, business units, team assignments,
and membership management with mocked DB connections. Uses sequential
side_effect returns to simulate multi-step workflows.
"""

import importlib.util
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


def _org_row(overrides=None):
    """Return a base organization row dict."""
    base = {
        "id": "org-001",
        "name": "Acme Corp",
        "slug": "acme-corp",
        "description": "Test organization",
        "max_budget": 10000.0,
        "allowed_models": ["gpt-4o"],
        "metadata": "{}",
        "is_active": True,
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
        "bu_count": 0,
        "team_count": 0,
        "member_count": 0,
    }
    if overrides:
        base.update(overrides)
    return base


def _bu_row(overrides=None):
    """Return a base business unit row dict."""
    base = {
        "id": "bu-001",
        "org_id": "org-001",
        "name": "Engineering",
        "slug": "engineering",
        "description": "Engineering BU",
        "max_budget": 5000.0,
        "allowed_models": ["gpt-4o"],
        "is_active": True,
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
    }
    if overrides:
        base.update(overrides)
    return base


def _team_row(overrides=None):
    """Return a base team hierarchy row dict."""
    base = {
        "team_id": "team-001",
        "org_id": "org-001",
        "bu_id": None,
        "max_budget_override": None,
        "created_at": "2026-01-01T00:00:00",
        "updated_at": None,
    }
    if overrides:
        base.update(overrides)
    return base


def _member_row(overrides=None):
    """Return a base membership row dict."""
    base = {
        "id": "mem-001",
        "user_id": "user-001",
        "email": "user@example.com",
        "display_name": "Test User",
        "org_id": "org-001",
        "role": "member",
        "bu_id": None,
        "created_at": "2026-01-01T00:00:00",
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
# 1. Create org returns organization
# ============================================================================


@pytest.mark.asyncio
async def test_create_org_returns_organization(client):
    """POST /organizations returns a full organization object."""
    row = _make_row(_org_row())
    conn = _make_async_conn(fetchrow_return=row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post("/api/v1/organizations", json={
            "name": "Acme Corp", "slug": "acme-corp",
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Acme Corp"
    assert data["slug"] == "acme-corp"
    assert data["id"] == "org-001"


# ============================================================================
# 2. Create org triggers audit
# ============================================================================


@pytest.mark.asyncio
async def test_create_org_triggers_audit(client):
    """POST /organizations calls log_audit_event after creation."""
    row = _make_row(_org_row())
    conn = _make_async_conn(fetchrow_return=row)
    deps.db_pool = _make_pool(conn)

    with patch("routers.organizations.log_audit_event", new_callable=AsyncMock) as mock_audit:
        async with client:
            resp = await client.post("/api/v1/organizations", json={
                "name": "Acme Corp", "slug": "acme-corp",
            })

        assert resp.status_code == 200
        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args
        assert call_kwargs.kwargs.get("action") == "create" or call_kwargs[1].get("action") == "create"


# ============================================================================
# 3. Org CRUD lifecycle
# ============================================================================


@pytest.mark.asyncio
async def test_org_crud_lifecycle(client):
    """Create -> get -> update -> delete lifecycle for organizations."""
    create_row = _make_row(_org_row())
    get_row = _make_row(_org_row({"bu_count": 2, "team_count": 3, "member_count": 5}))
    update_row = _make_row(_org_row({"name": "Acme Corp Updated"}))

    conn = _make_async_conn()
    conn.fetchrow = AsyncMock(side_effect=[create_row, get_row, update_row])
    conn.execute = AsyncMock(return_value="DELETE 1")
    deps.db_pool = _make_pool(conn)

    with patch("routers.organizations.log_audit_event", new_callable=AsyncMock):
        async with client:
            # Create
            r1 = await client.post("/api/v1/organizations", json={
                "name": "Acme Corp", "slug": "acme-corp",
            })
            assert r1.status_code == 200
            assert r1.json()["name"] == "Acme Corp"

            # Get
            r2 = await client.get("/api/v1/organizations/org-001")
            assert r2.status_code == 200
            assert r2.json()["bu_count"] == 2

            # Update
            r3 = await client.put("/api/v1/organizations/org-001", json={
                "name": "Acme Corp Updated",
            })
            assert r3.status_code == 200
            assert r3.json()["name"] == "Acme Corp Updated"

            # Delete
            r4 = await client.delete("/api/v1/organizations/org-001")
            assert r4.status_code == 200
            assert r4.json()["status"] == "deleted"


# ============================================================================
# 4. Business unit lifecycle
# ============================================================================


@pytest.mark.asyncio
async def test_business_unit_lifecycle(client):
    """Create BU -> update -> delete lifecycle."""
    create_row = _make_row(_bu_row())
    update_row = _make_row(_bu_row({"name": "Engineering V2"}))

    conn = _make_async_conn()
    conn.fetchrow = AsyncMock(side_effect=[create_row, update_row])
    conn.execute = AsyncMock(return_value="DELETE 1")
    deps.db_pool = _make_pool(conn)

    with patch("routers.organizations.log_audit_event", new_callable=AsyncMock):
        async with client:
            # Create
            r1 = await client.post("/api/v1/organizations/org-001/business-units", json={
                "name": "Engineering", "slug": "engineering",
            })
            assert r1.status_code == 200
            assert r1.json()["name"] == "Engineering"

            # Update
            r2 = await client.put("/api/v1/organizations/org-001/business-units/bu-001", json={
                "name": "Engineering V2",
            })
            assert r2.status_code == 200
            assert r2.json()["name"] == "Engineering V2"

            # Delete
            r3 = await client.delete("/api/v1/organizations/org-001/business-units/bu-001")
            assert r3.status_code == 200
            assert r3.json()["status"] == "deleted"


# ============================================================================
# 5. Team assignment lifecycle
# ============================================================================


@pytest.mark.asyncio
async def test_team_assignment(client):
    """Assign team -> list teams -> remove team."""
    team_row = _make_row(_team_row())

    conn = _make_async_conn()
    conn.execute = AsyncMock(side_effect=["INSERT 1", "DELETE 1"])
    conn.fetch = AsyncMock(return_value=[team_row])
    deps.db_pool = _make_pool(conn)

    with patch("routers.organizations.log_audit_event", new_callable=AsyncMock):
        async with client:
            # Assign
            r1 = await client.post("/api/v1/organizations/org-001/teams/team-001")
            assert r1.status_code == 200
            assert r1.json()["status"] == "assigned"

            # List
            r2 = await client.get("/api/v1/organizations/org-001/teams")
            assert r2.status_code == 200
            teams = r2.json()
            assert len(teams) == 1
            assert teams[0]["team_id"] == "team-001"

            # Remove
            r3 = await client.delete("/api/v1/organizations/org-001/teams/team-001")
            assert r3.status_code == 200
            assert r3.json()["status"] == "removed"


# ============================================================================
# 6. Membership lifecycle
# ============================================================================


@pytest.mark.asyncio
async def test_membership_lifecycle(client):
    """Add member -> update role -> remove member."""
    member_row = _make_row(_member_row())

    conn = _make_async_conn()
    conn.fetchrow = AsyncMock(return_value=member_row)
    conn.execute = AsyncMock(side_effect=["UPDATE 1", "DELETE 1"])
    deps.db_pool = _make_pool(conn)

    with patch("routers.organizations.log_audit_event", new_callable=AsyncMock):
        async with client:
            # Add member
            r1 = await client.post("/api/v1/organizations/org-001/members", json={
                "user_id": "user-001", "role": "member",
            })
            assert r1.status_code == 200
            assert r1.json()["user_id"] == "user-001"

            # Update role
            r2 = await client.put("/api/v1/organizations/org-001/members/user-001", json={
                "role": "admin",
            })
            assert r2.status_code == 200
            assert r2.json()["status"] == "updated"

            # Remove
            r3 = await client.delete("/api/v1/organizations/org-001/members/user-001")
            assert r3.status_code == 200
            assert r3.json()["status"] == "removed"


# ============================================================================
# 7. Delete org 404
# ============================================================================


@pytest.mark.asyncio
async def test_delete_org_404(client):
    """DELETE /organizations/{id} returns 404 for non-existent org."""
    conn = _make_async_conn(execute_return="DELETE 0")
    deps.db_pool = _make_pool(conn)

    with patch("routers.organizations.log_audit_event", new_callable=AsyncMock):
        async with client:
            resp = await client.delete("/api/v1/organizations/nonexistent")

    assert resp.status_code == 404
    assert "Organization not found" in resp.json()["detail"]


# ============================================================================
# 8. Create BU under org
# ============================================================================


@pytest.mark.asyncio
async def test_create_bu_under_org(client):
    """POST /organizations/{org_id}/business-units creates a BU."""
    row = _make_row(_bu_row({"org_id": "org-xyz"}))
    conn = _make_async_conn(fetchrow_return=row)
    deps.db_pool = _make_pool(conn)

    with patch("routers.organizations.log_audit_event", new_callable=AsyncMock):
        async with client:
            resp = await client.post("/api/v1/organizations/org-xyz/business-units", json={
                "name": "Data Science", "slug": "data-science",
            })

    assert resp.status_code == 200
    assert resp.json()["org_id"] == "org-xyz"


# ============================================================================
# 9. List orgs empty
# ============================================================================


@pytest.mark.asyncio
async def test_list_orgs_empty(client):
    """GET /organizations returns empty list when no orgs exist."""
    conn = _make_async_conn(fetch_return=[])
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/organizations")

    assert resp.status_code == 200
    assert resp.json() == []


# ============================================================================
# 10. List org members empty
# ============================================================================


@pytest.mark.asyncio
async def test_list_org_members_empty(client):
    """GET /organizations/{org_id}/members returns empty list."""
    conn = _make_async_conn(fetch_return=[])
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/organizations/org-001/members")

    assert resp.status_code == 200
    assert resp.json() == []


# ============================================================================
# 11. Update org no fields 400
# ============================================================================


@pytest.mark.asyncio
async def test_update_org_no_fields_400(client):
    """PUT /organizations/{id} with empty body returns 400."""
    conn = _make_async_conn()
    deps.db_pool = _make_pool(conn)

    with patch("routers.organizations.log_audit_event", new_callable=AsyncMock):
        async with client:
            resp = await client.put("/api/v1/organizations/org-001", json={})

    assert resp.status_code == 400
    assert "No fields to update" in resp.json()["detail"]


# ============================================================================
# 12. Get org not found 404
# ============================================================================


@pytest.mark.asyncio
async def test_get_org_not_found_404(client):
    """GET /organizations/{id} returns 404 when org does not exist."""
    conn = _make_async_conn(fetchrow_return=None)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/organizations/nonexistent")

    assert resp.status_code == 404
    assert "Organization not found" in resp.json()["detail"]


# ============================================================================
# 13. BU not found 404
# ============================================================================


@pytest.mark.asyncio
async def test_bu_not_found_404(client):
    """DELETE /organizations/{org_id}/business-units/{bu_id} returns 404."""
    conn = _make_async_conn(execute_return="DELETE 0")
    deps.db_pool = _make_pool(conn)

    with patch("routers.organizations.log_audit_event", new_callable=AsyncMock):
        async with client:
            resp = await client.delete("/api/v1/organizations/org-001/business-units/missing-bu")

    assert resp.status_code == 404
    assert "Business unit not found" in resp.json()["detail"]


# ============================================================================
# 14. Remove team not found 404
# ============================================================================


@pytest.mark.asyncio
async def test_remove_team_not_found_404(client):
    """DELETE /organizations/{org_id}/teams/{team_id} returns 404."""
    conn = _make_async_conn(execute_return="DELETE 0")
    deps.db_pool = _make_pool(conn)

    with patch("routers.organizations.log_audit_event", new_callable=AsyncMock):
        async with client:
            resp = await client.delete("/api/v1/organizations/org-001/teams/missing-team")

    assert resp.status_code == 404
    assert "Team assignment not found" in resp.json()["detail"]


# ============================================================================
# 15. Membership not found 404
# ============================================================================


@pytest.mark.asyncio
async def test_membership_not_found_404(client):
    """DELETE /organizations/{org_id}/members/{user_id} returns 404."""
    conn = _make_async_conn(execute_return="DELETE 0")
    deps.db_pool = _make_pool(conn)

    with patch("routers.organizations.log_audit_event", new_callable=AsyncMock):
        async with client:
            resp = await client.delete("/api/v1/organizations/org-001/members/missing-user")

    assert resp.status_code == 404
    assert "Membership not found" in resp.json()["detail"]


# ============================================================================
# 16. Org with counts from JOIN query
# ============================================================================


@pytest.mark.asyncio
async def test_org_with_counts(client):
    """GET /organizations/{id} returns bu_count, team_count, member_count."""
    row = _make_row(_org_row({"bu_count": 3, "team_count": 7, "member_count": 42}))
    conn = _make_async_conn(fetchrow_return=row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/organizations/org-001")

    assert resp.status_code == 200
    data = resp.json()
    assert data["bu_count"] == 3
    assert data["team_count"] == 7
    assert data["member_count"] == 42


# ============================================================================
# 17. Update member role
# ============================================================================


@pytest.mark.asyncio
async def test_update_member_role(client):
    """PUT /organizations/{org_id}/members/{user_id} updates role."""
    conn = _make_async_conn(execute_return="UPDATE 1")
    deps.db_pool = _make_pool(conn)

    with patch("routers.organizations.log_audit_event", new_callable=AsyncMock) as mock_audit:
        async with client:
            resp = await client.put("/api/v1/organizations/org-001/members/user-001", json={
                "role": "admin",
            })

    assert resp.status_code == 200
    assert resp.json()["status"] == "updated"
    mock_audit.assert_called_once()


# ============================================================================
# 18. List business units for org
# ============================================================================


@pytest.mark.asyncio
async def test_list_business_units_for_org(client):
    """GET /organizations/{org_id}/business-units returns BU list."""
    bu1 = _make_row(_bu_row({"id": "bu-1", "name": "Engineering"}))
    bu2 = _make_row(_bu_row({"id": "bu-2", "name": "Marketing"}))
    conn = _make_async_conn(fetch_return=[bu1, bu2])
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/organizations/org-001/business-units")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["name"] == "Engineering"
    assert data[1]["name"] == "Marketing"


# ============================================================================
# 19. Assign team with budget override
# ============================================================================


@pytest.mark.asyncio
async def test_assign_team_with_budget_override(client):
    """POST /organizations/{org_id}/teams/{team_id} with max_budget_override."""
    conn = _make_async_conn()
    conn.execute = AsyncMock(return_value="INSERT 1")
    deps.db_pool = _make_pool(conn)

    with patch("routers.organizations.log_audit_event", new_callable=AsyncMock):
        async with client:
            resp = await client.post("/api/v1/organizations/org-001/teams/team-001", json={
                "bu_id": "bu-001",
                "max_budget_override": 2500.0,
            })

    assert resp.status_code == 200
    assert resp.json()["status"] == "assigned"
    # Verify the execute was called with budget override
    call_args = conn.execute.call_args[0]
    assert 2500.0 in call_args


# ============================================================================
# 20. Remove member triggers audit
# ============================================================================


@pytest.mark.asyncio
async def test_remove_member_triggers_audit(client):
    """DELETE /organizations/{org_id}/members/{user_id} calls audit."""
    conn = _make_async_conn(execute_return="DELETE 1")
    deps.db_pool = _make_pool(conn)

    with patch("routers.organizations.log_audit_event", new_callable=AsyncMock) as mock_audit:
        async with client:
            resp = await client.delete("/api/v1/organizations/org-001/members/user-001")

    assert resp.status_code == 200
    mock_audit.assert_called_once()
    call_kwargs = mock_audit.call_args
    assert call_kwargs.kwargs.get("action") == "remove_member" or call_kwargs[1].get("action") == "remove_member"
