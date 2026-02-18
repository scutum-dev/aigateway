"""End-to-end workflow tests for the Admin API.

These tests run against the ASGI app with mocked DB/HTTP (same pattern as
the unit tests) but exercise multi-step workflows that span several endpoints.
"""

import importlib.util
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# ---------------------------------------------------------------------------
# Module loading (mirrors test_router_models.py pattern)
# ---------------------------------------------------------------------------

_service_dir = os.path.join(os.path.dirname(__file__), "../../src/admin-api")
sys.path.insert(0, _service_dir)

# Pre-mock OTEL
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
    _spec = importlib.util.spec_from_file_location(
        "admin_api_main", os.path.join(_service_dir, "main.py")
    )
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


def _mock_http_response(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


def _make_mock_row(data: dict):
    """Create a MagicMock that behaves like an asyncpg Record.

    Supports dict-style key access (row["key"]) and .get().
    """
    row = MagicMock()
    row.__getitem__ = lambda self, key: data[key]
    row.__contains__ = lambda self, key: key in data
    row.get = lambda key, default=None: data.get(key, default)
    row.keys = lambda: data.keys()
    row.values = lambda: data.values()
    row.items = lambda: data.items()
    return row


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


def _setup_db_pool():
    """Create and return a mock db_pool with a reusable connection mock."""
    pool = MagicMock()
    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__.return_value = conn
    ctx.__aexit__.return_value = None
    pool.acquire.return_value = ctx
    deps.db_pool = pool
    return pool, conn


# ============================================================================
# Org Setup Workflows
# ============================================================================


class TestOrgSetupWorkflow:
    """Multi-step organization setup scenarios."""

    @pytest.mark.asyncio
    async def test_create_org_returns_200(self, client):
        """Create org -> verify 200 with correct fields."""
        pool, conn = _setup_db_pool()
        conn.fetchrow.return_value = _make_mock_row({
            "id": "org-001",
            "name": "Acme Corp",
            "slug": "acme-corp",
            "description": "Test org",
            "max_budget": 10000.0,
            "allowed_models": ["gpt-4o"],
            "metadata": "{}",
            "is_active": True,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": None,
            "bu_count": 0,
            "team_count": 0,
            "member_count": 0,
        })
        conn.execute.return_value = "INSERT 1"

        async with client:
            resp = await client.post(
                "/api/v1/organizations",
                json={
                    "name": "Acme Corp",
                    "slug": "acme-corp",
                    "description": "Test org",
                    "max_budget": 10000.0,
                    "allowed_models": ["gpt-4o"],
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Acme Corp"
        assert data["slug"] == "acme-corp"
        assert data["id"] == "org-001"

    @pytest.mark.asyncio
    async def test_create_org_then_create_business_unit(self, client):
        """Create org -> create BU under it -> verify both return 200."""
        pool, conn = _setup_db_pool()

        org_row = _make_mock_row({
            "id": "org-001",
            "name": "Acme Corp",
            "slug": "acme-corp",
            "description": None,
            "max_budget": None,
            "allowed_models": None,
            "metadata": "{}",
            "is_active": True,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": None,
            "bu_count": 0,
            "team_count": 0,
            "member_count": 0,
        })

        bu_row = _make_mock_row({
            "id": "bu-001",
            "org_id": "org-001",
            "name": "Engineering",
            "slug": "engineering",
            "description": "Engineering department",
            "max_budget": 5000.0,
            "allowed_models": None,
            "is_active": True,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": None,
        })

        # fetchrow returns org row first, then bu row
        conn.fetchrow.side_effect = [org_row, bu_row]
        conn.execute.return_value = "INSERT 1"

        async with client:
            resp1 = await client.post(
                "/api/v1/organizations",
                json={"name": "Acme Corp", "slug": "acme-corp"},
            )
            assert resp1.status_code == 200

            resp2 = await client.post(
                "/api/v1/organizations/org-001/business-units",
                json={
                    "name": "Engineering",
                    "slug": "engineering",
                    "description": "Engineering department",
                    "max_budget": 5000.0,
                },
            )
            assert resp2.status_code == 200

        bu_data = resp2.json()
        assert bu_data["name"] == "Engineering"
        assert bu_data["org_id"] == "org-001"

    @pytest.mark.asyncio
    async def test_create_org_add_team_add_member(self, client):
        """Create org -> add team -> add member -> verify all return 200."""
        pool, conn = _setup_db_pool()

        org_row = _make_mock_row({
            "id": "org-001",
            "name": "Acme Corp",
            "slug": "acme-corp",
            "description": None,
            "max_budget": None,
            "allowed_models": None,
            "metadata": "{}",
            "is_active": True,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": None,
            "bu_count": 0,
            "team_count": 0,
            "member_count": 0,
        })

        member_row = _make_mock_row({
            "id": "mem-001",
            "user_id": "user-42",
            "email": None,
            "display_name": None,
            "org_id": "org-001",
            "role": "member",
            "bu_id": None,
            "created_at": "2026-01-01T00:00:00",
        })

        # Step 1: create org (fetchrow), step 2: assign team (execute), step 3: add member (fetchrow)
        conn.fetchrow.side_effect = [org_row, member_row]
        conn.execute.return_value = "INSERT 1"

        async with client:
            # Create org
            resp1 = await client.post(
                "/api/v1/organizations",
                json={"name": "Acme Corp", "slug": "acme-corp"},
            )
            assert resp1.status_code == 200

            # Assign team
            resp2 = await client.post(
                "/api/v1/organizations/org-001/teams/team-alpha",
                json={"bu_id": None, "max_budget_override": None},
            )
            assert resp2.status_code == 200
            assert resp2.json()["status"] == "assigned"

            # Add member
            resp3 = await client.post(
                "/api/v1/organizations/org-001/members",
                json={"user_id": "user-42", "role": "member"},
            )
            assert resp3.status_code == 200

        member_data = resp3.json()
        assert member_data["user_id"] == "user-42"
        assert member_data["role"] == "member"

    @pytest.mark.asyncio
    async def test_create_org_audit_event_logged(self, client):
        """Create org -> verify audit log_audit_event was called."""
        pool, conn = _setup_db_pool()

        org_row = _make_mock_row({
            "id": "org-audit-001",
            "name": "Audit Org",
            "slug": "audit-org",
            "description": None,
            "max_budget": None,
            "allowed_models": None,
            "metadata": "{}",
            "is_active": True,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": None,
            "bu_count": 0,
            "team_count": 0,
            "member_count": 0,
        })
        conn.fetchrow.return_value = org_row
        conn.execute.return_value = "INSERT 1"

        with patch("routers.organizations.log_audit_event", new_callable=AsyncMock) as mock_audit:
            async with client:
                resp = await client.post(
                    "/api/v1/organizations",
                    json={"name": "Audit Org", "slug": "audit-org"},
                )

            assert resp.status_code == 200
            mock_audit.assert_called_once()
            call_kwargs = mock_audit.call_args
            assert call_kwargs.kwargs["action"] == "create"
            assert call_kwargs.kwargs["resource_type"] == "organization"
            assert call_kwargs.kwargs["resource_id"] == "org-audit-001"

    @pytest.mark.asyncio
    async def test_update_org_audit_event_logged(self, client):
        """Update org -> verify audit event records 'update' action."""
        pool, conn = _setup_db_pool()

        updated_row = _make_mock_row({
            "id": "org-001",
            "name": "Acme Corp Updated",
            "slug": "acme-corp",
            "description": None,
            "max_budget": 20000.0,
            "allowed_models": None,
            "metadata": "{}",
            "is_active": True,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-02T00:00:00",
            "bu_count": 0,
            "team_count": 0,
            "member_count": 0,
        })
        conn.fetchrow.return_value = updated_row

        with patch("routers.organizations.log_audit_event", new_callable=AsyncMock) as mock_audit:
            async with client:
                resp = await client.put(
                    "/api/v1/organizations/org-001",
                    json={"name": "Acme Corp Updated", "max_budget": 20000.0},
                )

            assert resp.status_code == 200
            mock_audit.assert_called_once()
            assert mock_audit.call_args.kwargs["action"] == "update"

    @pytest.mark.asyncio
    async def test_delete_org_audit_event_logged(self, client):
        """Delete org -> verify audit event records 'delete' action."""
        pool, conn = _setup_db_pool()
        conn.execute.return_value = "DELETE 1"

        with patch("routers.organizations.log_audit_event", new_callable=AsyncMock) as mock_audit:
            async with client:
                resp = await client.delete("/api/v1/organizations/org-001")

            assert resp.status_code == 200
            assert resp.json()["status"] == "deleted"
            mock_audit.assert_called_once()
            assert mock_audit.call_args.kwargs["action"] == "delete"

    @pytest.mark.asyncio
    async def test_get_org_not_found_returns_404(self, client):
        """GET /organizations/{id} returns 404 when org does not exist."""
        pool, conn = _setup_db_pool()
        conn.fetchrow.return_value = None

        async with client:
            resp = await client.get("/api/v1/organizations/nonexistent")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_add_member_audit_event_logged(self, client):
        """Add org member -> verify audit records add_member action."""
        pool, conn = _setup_db_pool()

        member_row = _make_mock_row({
            "id": "mem-001",
            "user_id": "user-99",
            "email": None,
            "display_name": None,
            "org_id": "org-001",
            "role": "admin",
            "bu_id": None,
            "created_at": "2026-01-01T00:00:00",
        })
        conn.fetchrow.return_value = member_row
        conn.execute.return_value = "INSERT 1"

        with patch("routers.organizations.log_audit_event", new_callable=AsyncMock) as mock_audit:
            async with client:
                resp = await client.post(
                    "/api/v1/organizations/org-001/members",
                    json={"user_id": "user-99", "role": "admin"},
                )

            assert resp.status_code == 200
            mock_audit.assert_called_once()
            assert mock_audit.call_args.kwargs["action"] == "add_member"


# ============================================================================
# A/B Test Lifecycle
# ============================================================================


class TestABTestLifecycle:
    """A/B test create -> start -> collect metrics -> stop -> promote lifecycle."""

    @pytest.mark.asyncio
    async def test_create_ab_test(self, client):
        """Create an A/B test -> verify draft status."""
        pool, conn = _setup_db_pool()

        ab_row = _make_mock_row({
            "id": "ab-001",
            "name": "GPT-4o vs Claude",
            "status": "draft",
            "base_model": "gpt-4o",
            "variant_model": "claude-3-5-sonnet",
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
        })
        conn.fetchrow.return_value = ab_row

        async with client:
            resp = await client.post(
                "/api/v1/ab-tests",
                json={
                    "name": "GPT-4o vs Claude",
                    "base_model": "gpt-4o",
                    "variant_model": "claude-3-5-sonnet",
                    "traffic_split_percent": 10,
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "draft"
        assert data["base_model"] == "gpt-4o"
        assert data["variant_model"] == "claude-3-5-sonnet"

    @pytest.mark.asyncio
    async def test_create_start_stop_lifecycle(self, client):
        """Create -> start -> stop lifecycle with correct status transitions."""
        pool, conn = _setup_db_pool()
        deps.http_client = AsyncMock()

        # Step 1: create (fetchrow for INSERT RETURNING)
        draft_row = _make_mock_row({
            "id": "ab-002",
            "name": "Lifecycle Test",
            "status": "draft",
            "base_model": "gpt-4o",
            "variant_model": "claude-3-5-sonnet",
            "traffic_split_percent": 20,
            "success_metric": "cost_efficiency",
            "promotion_threshold": None,
            "rollback_threshold": None,
            "auto_promote": False,
            "auto_rollback": True,
            "started_at": None,
            "completed_at": None,
            "created_by": "test-admin",
            "created_at": "2026-01-01T00:00:00",
        })

        # Step 2: start - SELECT returns draft row, then UPDATE RETURNING returns running row
        running_row = _make_mock_row({
            "id": "ab-002",
            "name": "Lifecycle Test",
            "status": "running",
            "base_model": "gpt-4o",
            "variant_model": "claude-3-5-sonnet",
            "traffic_split_percent": 20,
            "success_metric": "cost_efficiency",
            "promotion_threshold": None,
            "rollback_threshold": None,
            "auto_promote": False,
            "auto_rollback": True,
            "started_at": "2026-01-01T01:00:00",
            "completed_at": None,
            "created_by": "test-admin",
            "created_at": "2026-01-01T00:00:00",
        })

        # Step 3: stop - SELECT returns running row, UPDATE RETURNING returns completed row
        completed_row = _make_mock_row({
            "id": "ab-002",
            "name": "Lifecycle Test",
            "status": "completed",
            "base_model": "gpt-4o",
            "variant_model": "claude-3-5-sonnet",
            "traffic_split_percent": 20,
            "success_metric": "cost_efficiency",
            "promotion_threshold": None,
            "rollback_threshold": None,
            "auto_promote": False,
            "auto_rollback": True,
            "started_at": "2026-01-01T01:00:00",
            "completed_at": "2026-01-01T02:00:00",
            "created_by": "test-admin",
            "created_at": "2026-01-01T00:00:00",
        })

        conn.fetchrow.side_effect = [
            draft_row,      # create
            draft_row,      # start: SELECT current status
            running_row,    # start: UPDATE RETURNING
            running_row,    # stop: SELECT current status
            completed_row,  # stop: UPDATE RETURNING
        ]

        # Mock LiteLLM responses for add/remove variant
        deps.http_client.post = AsyncMock(
            return_value=_mock_http_response(200, {"model_info": {"id": "litellm-variant-id"}})
        )
        deps.http_client.get = AsyncMock(
            return_value=_mock_http_response(200, {"data": []})
        )

        async with client:
            # Create
            resp1 = await client.post(
                "/api/v1/ab-tests",
                json={
                    "name": "Lifecycle Test",
                    "base_model": "gpt-4o",
                    "variant_model": "claude-3-5-sonnet",
                    "traffic_split_percent": 20,
                },
            )
            assert resp1.status_code == 200
            assert resp1.json()["status"] == "draft"

            # Start
            resp2 = await client.post("/api/v1/ab-tests/ab-002/start")
            assert resp2.status_code == 200
            assert resp2.json()["status"] == "running"

            # Stop
            resp3 = await client.post("/api/v1/ab-tests/ab-002/stop")
            assert resp3.status_code == 200
            assert resp3.json()["status"] == "completed"

    @pytest.mark.asyncio
    async def test_create_start_promote_lifecycle(self, client):
        """Create -> start -> promote -> verify completed status."""
        pool, conn = _setup_db_pool()
        deps.http_client = AsyncMock()

        draft_row = _make_mock_row({
            "id": "ab-003",
            "name": "Promote Test",
            "status": "draft",
            "base_model": "gpt-4o",
            "variant_model": "claude-3-5-sonnet",
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
        })

        running_row = _make_mock_row({
            "id": "ab-003",
            "name": "Promote Test",
            "status": "running",
            "base_model": "gpt-4o",
            "variant_model": "claude-3-5-sonnet",
            "traffic_split_percent": 10,
            "success_metric": "cost_efficiency",
            "promotion_threshold": None,
            "rollback_threshold": None,
            "auto_promote": False,
            "auto_rollback": True,
            "started_at": "2026-01-01T01:00:00",
            "completed_at": None,
            "created_by": "test-admin",
            "created_at": "2026-01-01T00:00:00",
        })

        promoted_row = _make_mock_row({
            "id": "ab-003",
            "name": "Promote Test",
            "status": "completed",
            "base_model": "gpt-4o",
            "variant_model": "claude-3-5-sonnet",
            "traffic_split_percent": 10,
            "success_metric": "cost_efficiency",
            "promotion_threshold": None,
            "rollback_threshold": None,
            "auto_promote": False,
            "auto_rollback": True,
            "started_at": "2026-01-01T01:00:00",
            "completed_at": "2026-01-01T02:00:00",
            "created_by": "test-admin",
            "created_at": "2026-01-01T00:00:00",
        })

        conn.fetchrow.side_effect = [
            draft_row,      # create
            draft_row,      # start: SELECT
            running_row,    # start: UPDATE RETURNING
            running_row,    # promote: SELECT
            promoted_row,   # promote: UPDATE RETURNING
        ]
        conn.execute.return_value = "INSERT 1"

        deps.http_client.post = AsyncMock(
            return_value=_mock_http_response(200, {"model_info": {"id": "variant-id"}})
        )
        deps.http_client.get = AsyncMock(
            return_value=_mock_http_response(200, {"data": []})
        )

        async with client:
            resp1 = await client.post(
                "/api/v1/ab-tests",
                json={
                    "name": "Promote Test",
                    "base_model": "gpt-4o",
                    "variant_model": "claude-3-5-sonnet",
                },
            )
            assert resp1.status_code == 200
            assert resp1.json()["status"] == "draft"

            resp2 = await client.post("/api/v1/ab-tests/ab-003/start")
            assert resp2.status_code == 200
            assert resp2.json()["status"] == "running"

            resp3 = await client.post("/api/v1/ab-tests/ab-003/promote")
            assert resp3.status_code == 200
            assert resp3.json()["status"] == "completed"

    @pytest.mark.asyncio
    async def test_start_already_running_test_returns_400(self, client):
        """Start a test that is already running -> 400 error."""
        pool, conn = _setup_db_pool()

        running_row = _make_mock_row({
            "id": "ab-004",
            "name": "Already Running",
            "status": "running",
            "base_model": "gpt-4o",
            "variant_model": "claude-3-5-sonnet",
            "traffic_split_percent": 10,
            "success_metric": "cost_efficiency",
            "promotion_threshold": None,
            "rollback_threshold": None,
            "auto_promote": False,
            "auto_rollback": True,
            "started_at": "2026-01-01T01:00:00",
            "completed_at": None,
            "created_by": "test-admin",
            "created_at": "2026-01-01T00:00:00",
        })
        conn.fetchrow.return_value = running_row

        async with client:
            resp = await client.post("/api/v1/ab-tests/ab-004/start")

        assert resp.status_code == 400
        assert "Cannot start test" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_stop_non_running_test_returns_400(self, client):
        """Stop a draft test -> 400 error."""
        pool, conn = _setup_db_pool()

        draft_row = _make_mock_row({
            "id": "ab-005",
            "name": "Draft Test",
            "status": "draft",
            "base_model": "gpt-4o",
            "variant_model": "claude-3-5-sonnet",
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
        })
        conn.fetchrow.return_value = draft_row

        async with client:
            resp = await client.post("/api/v1/ab-tests/ab-005/stop")

        assert resp.status_code == 400
        assert "not running" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_promote_non_running_test_returns_400(self, client):
        """Promote a draft test -> 400 error."""
        pool, conn = _setup_db_pool()

        draft_row = _make_mock_row({
            "id": "ab-006",
            "name": "Draft Promote",
            "status": "draft",
            "base_model": "gpt-4o",
            "variant_model": "claude-3-5-sonnet",
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
        })
        conn.fetchrow.return_value = draft_row

        async with client:
            resp = await client.post("/api/v1/ab-tests/ab-006/promote")

        assert resp.status_code == 400
        assert "not running" in resp.json()["detail"].lower()


# ============================================================================
# Prompt Workflow
# ============================================================================


class TestPromptWorkflow:
    """Prompt template create -> render -> approval lifecycle."""

    @pytest.mark.asyncio
    async def test_create_template_and_get_by_slug(self, client):
        """Create template -> get by slug -> verify fields match."""
        pool, conn = _setup_db_pool()

        template_row = _make_mock_row({
            "id": "tmpl-001",
            "name": "Summarizer",
            "slug": "summarizer",
            "description": "Summarize text",
            "category": "utility",
            "template_text": "Summarize the following: {{text}}",
            "variables": [{"name": "text", "type": "string", "required": True, "default": None}],
            "version": 1,
            "is_current": True,
            "status": "draft",
            "team_id": None,
            "model_hint": "gpt-4o-mini",
            "tags": ["summary", "utility"],
            "created_by": "test-admin",
            "approved_by": None,
            "approved_at": None,
            "is_active": True,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": None,
        })

        conn.fetchrow.side_effect = [template_row, template_row]

        async with client:
            # Create
            resp1 = await client.post(
                "/api/v1/prompts",
                json={
                    "name": "Summarizer",
                    "slug": "summarizer",
                    "description": "Summarize text",
                    "category": "utility",
                    "template_text": "Summarize the following: {{text}}",
                    "variables": [{"name": "text", "type": "string", "required": True}],
                    "model_hint": "gpt-4o-mini",
                    "tags": ["summary", "utility"],
                },
            )
            assert resp1.status_code == 200
            assert resp1.json()["slug"] == "summarizer"

            # Get by slug
            resp2 = await client.get("/api/v1/prompts/summarizer")
            assert resp2.status_code == 200
            assert resp2.json()["template_text"] == "Summarize the following: {{text}}"

    @pytest.mark.asyncio
    async def test_create_template_and_render(self, client):
        """Create template -> render with variables -> verify substitution."""
        pool, conn = _setup_db_pool()

        template_row = _make_mock_row({
            "id": "tmpl-002",
            "name": "Greeting",
            "slug": "greeting",
            "description": "Greeting template",
            "category": "utility",
            "template_text": "Hello {{name}}, welcome to {{company}}!",
            "variables": [
                {"name": "name", "type": "string", "required": True, "default": None},
                {"name": "company", "type": "string", "required": True, "default": None},
            ],
            "version": 1,
            "is_current": True,
            "status": "draft",
            "team_id": None,
            "model_hint": None,
            "tags": [],
            "created_by": "test-admin",
            "approved_by": None,
            "approved_at": None,
            "is_active": True,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": None,
        })

        # First fetchrow: create, second fetchrow: render (SELECT by slug)
        conn.fetchrow.side_effect = [template_row, template_row]

        async with client:
            # Create
            resp1 = await client.post(
                "/api/v1/prompts",
                json={
                    "name": "Greeting",
                    "slug": "greeting",
                    "template_text": "Hello {{name}}, welcome to {{company}}!",
                    "variables": [
                        {"name": "name", "type": "string", "required": True},
                        {"name": "company", "type": "string", "required": True},
                    ],
                },
            )
            assert resp1.status_code == 200

            # Render
            resp2 = await client.post(
                "/api/v1/prompts/greeting/render",
                json={"variables": {"name": "Alice", "company": "Acme"}},
            )
            assert resp2.status_code == 200

        render_data = resp2.json()
        assert render_data["rendered"] == "Hello Alice, welcome to Acme!"
        assert render_data["unresolved_variables"] == []

    @pytest.mark.asyncio
    async def test_render_with_unresolved_variables(self, client):
        """Render template with missing variables -> unresolved list populated."""
        pool, conn = _setup_db_pool()

        template_row = _make_mock_row({
            "id": "tmpl-003",
            "name": "Multi Var",
            "slug": "multi-var",
            "description": None,
            "category": None,
            "template_text": "{{greeting}} {{name}}, you have {{count}} items.",
            "variables": [],
            "version": 1,
            "is_current": True,
            "status": "draft",
            "team_id": None,
            "model_hint": None,
            "tags": [],
            "created_by": "test-admin",
            "approved_by": None,
            "approved_at": None,
            "is_active": True,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": None,
        })
        conn.fetchrow.return_value = template_row

        async with client:
            resp = await client.post(
                "/api/v1/prompts/multi-var/render",
                json={"variables": {"name": "Bob"}},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "Bob" in data["rendered"]
        assert "greeting" in data["unresolved_variables"]
        assert "count" in data["unresolved_variables"]

    @pytest.mark.asyncio
    async def test_submit_and_approve_prompt(self, client):
        """Create -> submit for review -> approve -> verify status transitions."""
        pool, conn = _setup_db_pool()

        template_row = _make_mock_row({
            "id": "tmpl-004",
            "name": "Review Me",
            "slug": "review-me",
            "description": None,
            "category": None,
            "template_text": "Test prompt",
            "variables": "[]",
            "version": 1,
            "is_current": True,
            "status": "draft",
            "team_id": None,
            "model_hint": None,
            "tags": [],
            "created_by": "test-admin",
            "approved_by": None,
            "approved_at": None,
            "is_active": True,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": None,
        })

        approval_row = _make_mock_row({
            "id": "approval-001",
            "template_id": "tmpl-004",
            "template_version": 1,
            "requested_by": "test-admin",
            "reviewer": None,
            "status": "pending",
            "comment": None,
            "requested_at": "2026-01-01T00:00:00",
            "reviewed_at": None,
        })

        pending_approval_row = _make_mock_row({
            "id": "approval-001",
            "template_id": "tmpl-004",
            "template_version": 1,
            "requested_by": "test-admin",
            "reviewer": None,
            "status": "pending",
            "comment": None,
            "requested_at": "2026-01-01T00:00:00",
            "reviewed_at": None,
        })

        # Sequence:
        # 1. create template (fetchrow)
        # 2. submit-review: SELECT template (fetchrow), then execute UPDATE, then INSERT approval (fetchrow)
        # 3. approve: SELECT approval (fetchrow), then execute UPDATE approval, then execute UPDATE template
        conn.fetchrow.side_effect = [
            template_row,        # create
            template_row,        # submit-review: SELECT template
            approval_row,        # submit-review: INSERT approval RETURNING
            pending_approval_row,  # approve: SELECT approval
        ]
        conn.execute.return_value = "UPDATE 1"

        async with client:
            # Create
            resp1 = await client.post(
                "/api/v1/prompts",
                json={
                    "name": "Review Me",
                    "slug": "review-me",
                    "template_text": "Test prompt",
                },
            )
            assert resp1.status_code == 200

            # Submit for review
            resp2 = await client.post("/api/v1/prompts/tmpl-004/submit-review")
            assert resp2.status_code == 200
            assert resp2.json()["status"] == "pending"

            # Approve
            resp3 = await client.post(
                "/api/v1/prompt-approvals/approval-001/approve",
                json={"comment": "Looks good!"},
            )
            assert resp3.status_code == 200
            assert resp3.json()["status"] == "approved"

    @pytest.mark.asyncio
    async def test_submit_review_nonexistent_template_returns_404(self, client):
        """Submit review for nonexistent template -> 404."""
        pool, conn = _setup_db_pool()
        conn.fetchrow.return_value = None

        async with client:
            resp = await client.post("/api/v1/prompts/nonexistent-id/submit-review")

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_approve_already_reviewed_returns_404(self, client):
        """Approve an already-reviewed approval -> 404."""
        pool, conn = _setup_db_pool()
        conn.fetchrow.return_value = None  # No pending approval found

        async with client:
            resp = await client.post("/api/v1/prompt-approvals/gone-id/approve")

        assert resp.status_code == 404
        assert "already reviewed" in resp.json()["detail"].lower() or "not found" in resp.json()["detail"].lower()


# ============================================================================
# Cross-Feature Flows
# ============================================================================


class TestCrossFeatureFlows:
    """Workflows that span multiple feature areas."""

    @pytest.mark.asyncio
    async def test_create_deprecation_check_status_sync_alias(self, client):
        """Create deprecation -> check status -> sync alias to LiteLLM."""
        pool, conn = _setup_db_pool()
        deps.http_client = AsyncMock()

        deprecation_row = _make_mock_row({
            "id": "dep-001",
            "model_name": "gpt-3.5-turbo",
            "replacement_model": "gpt-4o-mini",
            "deprecation_date": "2025-12-01",
            "sunset_date": "2026-06-01",
            "message": "GPT-3.5-turbo is deprecated, use gpt-4o-mini",
            "created_at": "2025-11-01T00:00:00",
        })

        # Sequence:
        # 1. create: fetchrow for existing check (returns None), fetchrow for INSERT
        # 2. check: fetchrow for SELECT
        # 3. sync-alias: fetchrow for SELECT deprecation
        conn.fetchrow.side_effect = [
            None,              # create: no existing deprecation
            deprecation_row,   # create: INSERT RETURNING
            deprecation_row,   # check: SELECT
            deprecation_row,   # sync-alias: SELECT
        ]

        deps.http_client.post = AsyncMock(
            return_value=_mock_http_response(200, {
                "model_name": "gpt-3.5-turbo",
                "model_info": {"id": "alias-model-id"},
            })
        )

        async with client:
            # Create deprecation
            resp1 = await client.post(
                "/api/v1/model-deprecations",
                json={
                    "model_name": "gpt-3.5-turbo",
                    "replacement_model": "gpt-4o-mini",
                    "deprecation_date": "2025-12-01",
                    "sunset_date": "2026-06-01",
                    "message": "GPT-3.5-turbo is deprecated, use gpt-4o-mini",
                },
            )
            assert resp1.status_code == 200
            assert resp1.json()["model_name"] == "gpt-3.5-turbo"

            # Check deprecation status
            resp2 = await client.get("/api/v1/model-deprecations/check/gpt-3.5-turbo")
            assert resp2.status_code == 200
            assert resp2.json()["deprecated"] is True

            # Sync alias to LiteLLM
            resp3 = await client.post("/api/v1/model-deprecations/dep-001/sync-alias")
            assert resp3.status_code == 200
            assert resp3.json()["status"] == "synced"
            assert resp3.json()["replacement_model"] == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_sync_alias_no_replacement_returns_400(self, client):
        """Sync alias with no replacement model -> 400."""
        pool, conn = _setup_db_pool()

        dep_row = _make_mock_row({
            "id": "dep-002",
            "model_name": "old-model",
            "replacement_model": None,
            "deprecation_date": None,
            "sunset_date": None,
            "message": None,
            "created_at": "2026-01-01T00:00:00",
        })
        conn.fetchrow.return_value = dep_row

        async with client:
            resp = await client.post("/api/v1/model-deprecations/dep-002/sync-alias")

        assert resp.status_code == 400
        assert "No replacement model" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_duplicate_deprecation_returns_409(self, client):
        """Create deprecation for model that already has one -> 409."""
        pool, conn = _setup_db_pool()

        existing_row = _make_mock_row({"id": "dep-existing"})
        conn.fetchrow.return_value = existing_row

        async with client:
            resp = await client.post(
                "/api/v1/model-deprecations",
                json={
                    "model_name": "already-deprecated",
                    "replacement_model": "new-model",
                },
            )

        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_sync_alias_litellm_error_returns_502(self, client):
        """Sync alias when LiteLLM returns 500 -> 502."""
        pool, conn = _setup_db_pool()
        deps.http_client = AsyncMock()

        dep_row = _make_mock_row({
            "id": "dep-003",
            "model_name": "old-model",
            "replacement_model": "new-model",
            "deprecation_date": None,
            "sunset_date": None,
            "message": None,
            "created_at": "2026-01-01T00:00:00",
        })
        conn.fetchrow.return_value = dep_row

        deps.http_client.post = AsyncMock(
            return_value=_mock_http_response(500, text="Internal Server Error")
        )

        async with client:
            resp = await client.post("/api/v1/model-deprecations/dep-003/sync-alias")

        assert resp.status_code == 502

    @pytest.mark.asyncio
    async def test_sso_create_and_test_connection(self, client):
        """Create org SSO config -> test connection -> verify results."""
        pool, conn = _setup_db_pool()
        deps.http_client = AsyncMock()

        sso_row = _make_mock_row({
            "id": "sso-001",
            "org_id": "org-001",
            "provider_type": "oidc",
            "provider_name": "Okta",
            "client_id": "client-id-123",
            "client_secret_encrypted": "encrypted-secret",
            "issuer_url": "https://dev-123.okta.com",
            "authorization_url": None,
            "token_url": None,
            "userinfo_url": None,
            "jwks_uri": None,
            "saml_metadata_url": None,
            "scopes": "openid email profile",
            "group_claim": "groups",
            "group_to_org_mapping": "{}",
            "is_active": True,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": None,
        })

        # create SSO: fetchrow for INSERT
        # test SSO: fetchrow for SELECT
        conn.fetchrow.side_effect = [sso_row, sso_row]
        conn.execute.return_value = "INSERT 1"

        # Mock OIDC discovery response
        discovery_resp = _mock_http_response(200, {
            "issuer": "https://dev-123.okta.com",
            "authorization_endpoint": "https://dev-123.okta.com/authorize",
            "token_endpoint": "https://dev-123.okta.com/token",
            "userinfo_endpoint": "https://dev-123.okta.com/userinfo",
            "scopes_supported": ["openid", "email", "profile"],
        })
        deps.http_client.get = AsyncMock(return_value=discovery_resp)

        with patch("routers.sso.log_audit_event", new_callable=AsyncMock):
            async with client:
                # Create SSO config
                resp1 = await client.post(
                    "/api/v1/organizations/org-001/sso",
                    json={
                        "provider_type": "oidc",
                        "provider_name": "Okta",
                        "client_id": "client-id-123",
                        "client_secret": "secret-value",
                        "issuer_url": "https://dev-123.okta.com",
                    },
                )
                assert resp1.status_code == 200
                assert resp1.json()["provider_type"] == "oidc"

                # Test SSO connection
                resp2 = await client.post("/api/v1/organizations/org-001/sso/test")
                assert resp2.status_code == 200

        test_data = resp2.json()
        assert test_data["status"] == "ok"
        assert "working" in test_data["message"].lower()


# ============================================================================
# Rate Limit + Audit
# ============================================================================


class TestRateLimitAndAudit:
    """Rate limit policy workflows with event tracking."""

    @pytest.mark.asyncio
    async def test_create_rate_limit_policy(self, client):
        """Create rate limit policy -> verify returned fields."""
        pool, conn = _setup_db_pool()
        deps.http_client = AsyncMock()

        policy_row = _make_mock_row({
            "id": "rl-001",
            "name": "Team Alpha Rate Limit",
            "description": "Rate limit for team alpha",
            "scope": "team",
            "scope_value": "team-alpha",
            "rpm_limit": 100,
            "tpm_limit": 50000,
            "rpd_limit": 10000,
            "tpd_limit": 5000000,
            "burst_multiplier": 1.5,
            "burst_window_seconds": 10,
            "priority": 1,
            "is_active": True,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": None,
        })
        conn.fetchrow.return_value = policy_row

        # Mock the LiteLLM sync call
        deps.http_client.post = AsyncMock(
            return_value=_mock_http_response(200, {})
        )

        async with client:
            resp = await client.post(
                "/api/v1/rate-limits",
                json={
                    "name": "Team Alpha Rate Limit",
                    "description": "Rate limit for team alpha",
                    "scope": "team",
                    "scope_value": "team-alpha",
                    "rpm_limit": 100,
                    "tpm_limit": 50000,
                    "rpd_limit": 10000,
                    "tpd_limit": 5000000,
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Team Alpha Rate Limit"
        assert data["scope"] == "team"
        assert data["rpm_limit"] == 100

    @pytest.mark.asyncio
    async def test_create_policy_and_get_status(self, client):
        """Create policy -> get rate limit status -> verify status response."""
        pool, conn = _setup_db_pool()
        deps.http_client = AsyncMock()
        deps.redis_client = None  # Force counters to be 0

        policy_row = _make_mock_row({
            "id": "rl-002",
            "name": "User Rate Limit",
            "description": None,
            "scope": "user",
            "scope_value": "user-42",
            "rpm_limit": 60,
            "tpm_limit": 10000,
            "rpd_limit": None,
            "tpd_limit": None,
            "burst_multiplier": 1.5,
            "burst_window_seconds": 10,
            "priority": 0,
            "is_active": True,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": None,
        })

        # create: fetchrow, status: fetch (returns list)
        conn.fetchrow.return_value = policy_row
        conn.fetch.return_value = [policy_row]

        deps.http_client.post = AsyncMock(
            return_value=_mock_http_response(200, {})
        )

        async with client:
            # Create
            resp1 = await client.post(
                "/api/v1/rate-limits",
                json={
                    "name": "User Rate Limit",
                    "scope": "user",
                    "scope_value": "user-42",
                    "rpm_limit": 60,
                    "tpm_limit": 10000,
                },
            )
            assert resp1.status_code == 200

            # Get status
            resp2 = await client.get("/api/v1/rate-limits/status")
            assert resp2.status_code == 200

        status_data = resp2.json()
        assert isinstance(status_data, list)
        assert len(status_data) >= 1
        assert status_data[0]["scope"] == "user"
        assert status_data[0]["rpm_limit"] == 60

    @pytest.mark.asyncio
    async def test_create_policy_and_list_events(self, client):
        """Create policy -> list rate limit events -> verify event list."""
        pool, conn = _setup_db_pool()
        deps.http_client = AsyncMock()

        policy_row = _make_mock_row({
            "id": "rl-003",
            "name": "Global Limit",
            "description": None,
            "scope": "global",
            "scope_value": None,
            "rpm_limit": 1000,
            "tpm_limit": None,
            "rpd_limit": None,
            "tpd_limit": None,
            "burst_multiplier": 2.0,
            "burst_window_seconds": 15,
            "priority": 10,
            "is_active": True,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": None,
        })

        event_row = _make_mock_row({
            "id": "evt-001",
            "policy_id": "rl-003",
            "scope": "global",
            "scope_value": None,
            "limit_type": "rpm",
            "current_value": 1100,
            "limit_value": 1000,
            "action": "rejected",
            "created_at": "2026-01-01T01:00:00",
        })

        conn.fetchrow.return_value = policy_row
        # First fetch: for create (not used since create uses fetchrow)
        # Then fetch: for list events
        conn.fetch.return_value = [event_row]

        deps.http_client.post = AsyncMock(
            return_value=_mock_http_response(200, {})
        )

        async with client:
            # Create policy
            resp1 = await client.post(
                "/api/v1/rate-limits",
                json={
                    "name": "Global Limit",
                    "scope": "global",
                    "rpm_limit": 1000,
                },
            )
            assert resp1.status_code == 200

            # List events
            resp2 = await client.get("/api/v1/rate-limit-events")
            assert resp2.status_code == 200

        events = resp2.json()
        assert isinstance(events, list)
        assert len(events) == 1
        assert events[0]["action"] == "rejected"
        assert events[0]["scope"] == "global"

    @pytest.mark.asyncio
    async def test_invalid_scope_returns_400(self, client):
        """Create rate limit with invalid scope -> 400."""
        pool, conn = _setup_db_pool()

        async with client:
            resp = await client.post(
                "/api/v1/rate-limits",
                json={
                    "name": "Bad Scope",
                    "scope": "nonexistent_scope",
                    "rpm_limit": 100,
                },
            )

        assert resp.status_code == 400
        assert "Invalid scope" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_delete_rate_limit_policy_clears_litellm(self, client):
        """Delete rate limit -> verify LiteLLM sync called to clear limits."""
        pool, conn = _setup_db_pool()
        deps.http_client = AsyncMock()

        policy_row = _make_mock_row({
            "scope": "team",
            "scope_value": "team-beta",
        })

        # First fetchrow: SELECT to get scope info, then execute: DELETE
        conn.fetchrow.return_value = policy_row
        conn.execute.return_value = "DELETE 1"

        deps.http_client.post = AsyncMock(
            return_value=_mock_http_response(200, {})
        )

        async with client:
            resp = await client.delete("/api/v1/rate-limits/rl-001")

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        # Verify LiteLLM was called to clear limits
        deps.http_client.post.assert_called_once()


# ============================================================================
# Event System Workflows
# ============================================================================


class TestEventSystemWorkflow:
    """Event subscription and event log workflows."""

    @pytest.mark.asyncio
    async def test_create_subscription_and_send_test_event(self, client):
        """Create event subscription -> send test event -> list events."""
        pool, conn = _setup_db_pool()

        subscription_row = _make_mock_row({
            "id": "sub-001",
            "name": "Slack Alerts",
            "event_types": ["sla.violation", "budget.exceeded"],
            "channel": "slack",
            "config": json.dumps({"webhook_url": "https://hooks.slack.com/test"}),
            "filters": None,
            "is_active": True,
            "created_at": "2026-01-01T00:00:00",
        })

        event_row = _make_mock_row({
            "id": "ev-001",
            "event_type": "sla.violation",
            "payload": json.dumps({"provider": "openai", "violation": "p95_latency"}),
            "source_service": "admin-api-test",
            "created_at": "2026-01-01T01:00:00",
        })

        # create subscription: fetchrow, send test event: fetchrow, list events: fetch
        conn.fetchrow.side_effect = [subscription_row, event_row]
        conn.fetch.return_value = [event_row]

        async with client:
            # Create subscription
            resp1 = await client.post(
                "/api/v1/events/subscriptions",
                json={
                    "name": "Slack Alerts",
                    "event_types": ["sla.violation", "budget.exceeded"],
                    "channel": "slack",
                    "config": {"webhook_url": "https://hooks.slack.com/test"},
                },
            )
            assert resp1.status_code == 200
            assert resp1.json()["channel"] == "slack"

            # Send test event
            resp2 = await client.post(
                "/api/v1/events/test",
                json={
                    "event_type": "sla.violation",
                    "payload": {"provider": "openai", "violation": "p95_latency"},
                },
            )
            assert resp2.status_code == 200
            assert resp2.json()["event_type"] == "sla.violation"

            # List events
            resp3 = await client.get("/api/v1/events/log")
            assert resp3.status_code == 200

        events = resp3.json()
        assert isinstance(events, list)
        assert len(events) == 1
        assert events[0]["event_type"] == "sla.violation"

    @pytest.mark.asyncio
    async def test_create_update_delete_subscription(self, client):
        """Full subscription lifecycle: create -> update -> delete."""
        pool, conn = _setup_db_pool()

        sub_row = _make_mock_row({
            "id": "sub-002",
            "name": "Email Alerts",
            "event_types": ["budget.exceeded"],
            "channel": "email",
            "config": json.dumps({"to": "admin@acme.com"}),
            "filters": None,
            "is_active": True,
            "created_at": "2026-01-01T00:00:00",
        })

        updated_row = _make_mock_row({
            "id": "sub-002",
            "name": "Email Alerts - Updated",
            "event_types": ["budget.exceeded", "sla.violation"],
            "channel": "email",
            "config": json.dumps({"to": "team@acme.com"}),
            "filters": None,
            "is_active": True,
            "created_at": "2026-01-01T00:00:00",
        })

        # create: fetchrow, update: fetchrow (existing check), fetchrow (updated), delete: execute
        conn.fetchrow.side_effect = [sub_row, sub_row, updated_row]
        conn.execute.return_value = "DELETE 1"

        async with client:
            # Create
            resp1 = await client.post(
                "/api/v1/events/subscriptions",
                json={
                    "name": "Email Alerts",
                    "event_types": ["budget.exceeded"],
                    "channel": "email",
                    "config": {"to": "admin@acme.com"},
                },
            )
            assert resp1.status_code == 200

            # Update
            resp2 = await client.put(
                "/api/v1/events/subscriptions/sub-002",
                json={
                    "name": "Email Alerts - Updated",
                    "event_types": ["budget.exceeded", "sla.violation"],
                    "config": {"to": "team@acme.com"},
                },
            )
            assert resp2.status_code == 200
            assert resp2.json()["name"] == "Email Alerts - Updated"

            # Delete
            resp3 = await client.delete("/api/v1/events/subscriptions/sub-002")
            assert resp3.status_code == 200
            assert resp3.json()["status"] == "ok"


# ============================================================================
# Audit Log Querying
# ============================================================================


class TestAuditLogQuerying:
    """Audit log list and export workflows."""

    @pytest.mark.asyncio
    async def test_list_audit_logs_with_filters(self, client):
        """List audit logs with resource_type filter."""
        pool, conn = _setup_db_pool()

        audit_row = _make_mock_row({
            "id": "log-001",
            "timestamp": "2026-01-01T00:00:00+00:00",
            "actor_id": "test-admin",
            "actor_email": "admin@acme.com",
            "actor_ip": "127.0.0.1",
            "org_id": None,
            "action": "create",
            "resource_type": "organization",
            "resource_id": "org-001",
            "resource_name": "Acme Corp",
            "changes": "{}",
            "request_metadata": "{}",
            "created_at": "2026-01-01T00:00:00",
        })
        conn.fetch.return_value = [audit_row]

        async with client:
            resp = await client.get(
                "/api/v1/audit-logs",
                params={"resource_type": "organization"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["action"] == "create"
        assert data[0]["resource_type"] == "organization"

    @pytest.mark.asyncio
    async def test_export_audit_logs_json(self, client):
        """Export audit logs as JSON."""
        pool, conn = _setup_db_pool()

        audit_row = _make_mock_row({
            "id": "log-002",
            "timestamp": "2026-01-01T00:00:00+00:00",
            "actor_id": "test-admin",
            "actor_email": None,
            "actor_ip": None,
            "org_id": None,
            "action": "delete",
            "resource_type": "team",
            "resource_id": "team-001",
            "resource_name": "Team Alpha",
            "changes": "{}",
            "request_metadata": "{}",
            "created_at": "2026-01-01T00:00:00",
        })
        conn.fetch.return_value = [audit_row]

        async with client:
            resp = await client.get(
                "/api/v1/audit-logs/export",
                params={"format": "json"},
            )

        assert resp.status_code == 200
        # JSON export returns streaming response
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["action"] == "delete"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
