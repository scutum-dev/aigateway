"""Unit tests for the Admin API router modules.

Tests Models, Policies, Budgets, Teams, Keys, and Settings routers by:
1. Loading admin-api modules via importlib (same pattern as test_auth.py)
2. Mocking deps.db_pool, deps.http_client, deps.redis_client before each test
3. Using httpx.ASGITransport to test the full FastAPI app
4. Overriding auth dependencies to bypass JWT validation
"""

import importlib.util
import os
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

# ---------------------------------------------------------------------------
# Module loading (mirrors test_auth.py pattern)
# ---------------------------------------------------------------------------

_service_dir = os.path.join(os.path.dirname(__file__), "../../src/admin-api")
sys.path.insert(0, _service_dir)

# We need to pre-mock heavy dependencies that main.py imports at module level
# so the import does not fail when those packages are not installed or when
# side-effects (like OTEL tracer setup) fire.

# Mock opentelemetry modules before importing main
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

# Mock alembic so migrations don't run
_alembic_mock = MagicMock()
sys.modules.setdefault("alembic", _alembic_mock)
sys.modules.setdefault("alembic.config", _alembic_mock)
sys.modules.setdefault("alembic.command", _alembic_mock)

# Now import the admin-api modules
_spec = importlib.util.spec_from_file_location("admin_api_main", os.path.join(_service_dir, "main.py"))
_main_mod = importlib.util.module_from_spec(_spec)
sys.modules["admin_api_main"] = _main_mod
_spec.loader.exec_module(_main_mod)

app = _main_mod.app

# Import deps and auth from the already-loaded service path
import deps  # noqa: E402
from auth import UserInfo, get_current_user, require_admin  # noqa: E402

# ---------------------------------------------------------------------------
# Auth override -- bypass JWT for all endpoints
# ---------------------------------------------------------------------------


def _fake_user():
    return UserInfo(user_id="test-admin", role="admin", is_admin=True)


app.dependency_overrides[get_current_user] = _fake_user
app.dependency_overrides[require_admin] = _fake_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_async_conn(
    fetch_return=None,
    fetchrow_return=None,
    execute_return=None,
):
    """Build a mock asyncpg connection with configurable return values."""
    conn = AsyncMock()
    conn.fetch.return_value = fetch_return if fetch_return is not None else []
    conn.fetchrow.return_value = fetchrow_return
    conn.execute.return_value = execute_return or "DELETE 1"
    return conn


def _make_pool(conn):
    """Wrap a mock connection in a pool that supports `async with pool.acquire()`."""
    pool = MagicMock()
    ctx = AsyncMock()
    ctx.__aenter__.return_value = conn
    ctx.__aexit__.return_value = None
    pool.acquire.return_value = ctx
    return pool


@pytest.fixture(autouse=True)
def _reset_deps():
    """Ensure deps state is clean before and after each test."""
    original_pool = deps.db_pool
    original_http = deps.http_client
    original_redis = deps.redis_client

    # Reset the rate-limit cache so it doesn't bleed across tests
    _main_mod._rate_limit_cache["value"] = None
    _main_mod._rate_limit_cache["expires_at"] = 0.0
    _main_mod._inmemory_requests.clear()

    yield

    deps.db_pool = original_pool
    deps.http_client = original_http
    deps.redis_client = original_redis


# ---------------------------------------------------------------------------
# Client helper
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """Return an httpx.AsyncClient wired to the FastAPI app."""
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# ============================================================================
# Models Router
# ============================================================================


class TestModelsRouter:
    """Tests for /api/v1/models endpoints."""

    @pytest.mark.asyncio
    async def test_list_models(self, client):
        """GET /models returns model list from DB."""
        rows = [
            {
                "model_id": "gpt-4o",
                "provider": "openai",
                "tier": "premium",
                "cost_per_1k_input": 0.005,
                "cost_per_1k_output": 0.015,
                "supports_streaming": True,
                "supports_function_calling": True,
                "default_latency_sla_ms": 3000,
            },
            {
                "model_id": "claude-3-5-sonnet",
                "provider": "anthropic",
                "tier": "premium",
                "cost_per_1k_input": 0.003,
                "cost_per_1k_output": 0.015,
                "supports_streaming": True,
                "supports_function_calling": True,
                "default_latency_sla_ms": 4000,
            },
        ]
        conn = _make_async_conn(fetch_return=rows)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/models")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["model_id"] == "gpt-4o"
        assert data[1]["provider"] == "anthropic"

    @pytest.mark.asyncio
    async def test_update_model(self, client):
        """PUT /models/{model_id} returns updated model on success."""
        returned_row = {
            "model_id": "gpt-4o",
            "provider": "openai",
            "tier": "economy",
            "cost_per_1k_input": 0.002,
            "cost_per_1k_output": 0.006,
            "supports_streaming": True,
            "supports_function_calling": True,
            "supports_vision": False,
            "default_latency_sla_ms": 5000,
            "is_active": True,
        }
        conn = _make_async_conn(fetchrow_return=returned_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.put(
                "/api/v1/models/gpt-4o",
                json={"tier": "economy"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "economy"
        assert data["model_id"] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_update_model_not_found(self, client):
        """PUT /models/{model_id} returns 404 when model doesn't exist."""
        conn = _make_async_conn(fetchrow_return=None)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.put(
                "/api/v1/models/nonexistent",
                json={"tier": "economy"},
            )

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_update_model_no_changes(self, client):
        """PUT /models/{model_id} returns 400 when body has no real updates."""
        conn = _make_async_conn()
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.put(
                "/api/v1/models/gpt-4o",
                json={},
            )

        assert resp.status_code == 400
        assert "no updates" in resp.json()["detail"].lower()


# ============================================================================
# Policies Router
# ============================================================================


class TestPoliciesRouter:
    """Tests for /api/v1/routing-policies endpoints."""

    @pytest.mark.asyncio
    async def test_list_policies(self, client):
        """GET /routing-policies returns policy list from DB."""
        rows = [
            {
                "id": "1",
                "name": "cost-opt",
                "description": "Optimise for cost",
                "priority": 10,
                "condition": "true",
                "action": "permit",
                "target_models": ["gpt-4o-mini"],
                "is_active": True,
            },
        ]
        conn = _make_async_conn(fetch_return=rows)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/routing-policies")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "cost-opt"

    @pytest.mark.asyncio
    async def test_create_policy(self, client):
        """POST /routing-policies inserts and returns new policy."""
        returned_row = {
            "id": "42",
            "name": "new-policy",
            "description": "Test policy",
            "priority": 5,
            "condition": "when { true }",
            "action": "permit",
            "target_models": ["gpt-4o"],
            "is_active": True,
        }
        conn = _make_async_conn(fetchrow_return=returned_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.post(
                "/api/v1/routing-policies",
                json={
                    "name": "new-policy",
                    "description": "Test policy",
                    "priority": 5,
                    "condition": "when { true }",
                    "action": "permit",
                    "target_models": ["gpt-4o"],
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "42"
        assert data["name"] == "new-policy"

    @pytest.mark.asyncio
    async def test_delete_policy(self, client):
        """DELETE /routing-policies/{id} returns success."""
        conn = _make_async_conn(execute_return="DELETE 1")
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.delete("/api/v1/routing-policies/42")

        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    @pytest.mark.asyncio
    async def test_delete_policy_not_found(self, client):
        """DELETE /routing-policies/{id} returns 404 when not found."""
        conn = _make_async_conn(execute_return="DELETE 0")
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.delete("/api/v1/routing-policies/999")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# ============================================================================
# Budgets Router
# ============================================================================


class TestBudgetsRouter:
    """Tests for /api/v1/budgets endpoints."""

    _budget_row = {
        "id": "1",
        "name": "team-budget",
        "entity_type": "team",
        "entity_id": "team-42",
        "monthly_limit": 500.0,
        "current_spend": 123.45,
        "soft_limit_percent": 0.8,
        "hard_limit_percent": 1.0,
        "alert_email": "admin@example.com",
        "is_active": True,
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2025, 6, 1, tzinfo=timezone.utc),
    }

    @pytest.mark.asyncio
    async def test_list_budgets(self, client):
        """GET /budgets returns budget list."""
        conn = _make_async_conn(fetch_return=[self._budget_row])
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/budgets")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "team-budget"
        assert data[0]["monthly_limit"] == 500.0

    @pytest.mark.asyncio
    async def test_create_budget(self, client):
        """POST /budgets inserts and returns new budget."""
        conn = _make_async_conn(fetchrow_return=self._budget_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.post(
                "/api/v1/budgets",
                json={
                    "name": "team-budget",
                    "entity_type": "team",
                    "entity_id": "team-42",
                    "monthly_limit": 500.0,
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_type"] == "team"

    @pytest.mark.asyncio
    async def test_update_budget(self, client):
        """PUT /budgets/{id} returns updated budget."""
        updated_row = {**self._budget_row, "monthly_limit": 750.0}
        conn = _make_async_conn(fetchrow_return=updated_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.put(
                "/api/v1/budgets/1",
                json={"monthly_limit": 750.0},
            )

        assert resp.status_code == 200
        assert resp.json()["monthly_limit"] == 750.0

    @pytest.mark.asyncio
    async def test_update_budget_not_found(self, client):
        """PUT /budgets/{id} returns 404 when budget doesn't exist."""
        conn = _make_async_conn(fetchrow_return=None)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.put(
                "/api/v1/budgets/999",
                json={"monthly_limit": 100.0},
            )

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# ============================================================================
# Teams Router
# ============================================================================


class TestTeamsRouter:
    """Tests for /api/v1/teams endpoints."""

    @pytest.mark.asyncio
    async def test_list_teams(self, client):
        """GET /teams returns teams with members populated."""
        team_row = {
            "id": "t-1",
            "name": "Platform Team",
            "description": "Infra team",
            "monthly_budget": 1000.0,
            "default_model": "gpt-4o",
            "is_active": True,
            "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        }
        member_rows = [{"user_id": "alice"}, {"user_id": "bob"}]

        conn = AsyncMock()
        # First call: fetch teams; second call: fetch members for that team
        conn.fetch.side_effect = [[team_row], member_rows]
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/teams")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Platform Team"
        assert set(data[0]["members"]) == {"alice", "bob"}

    @pytest.mark.asyncio
    async def test_create_team(self, client):
        """POST /teams inserts and returns new team."""
        returned_row = {
            "id": "t-new",
            "name": "New Team",
            "description": "A new team",
            "monthly_budget": 200.0,
            "default_model": None,
            "is_active": True,
            "created_at": datetime(2025, 6, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2025, 6, 1, tzinfo=timezone.utc),
        }
        conn = _make_async_conn(fetchrow_return=returned_row)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.post(
                "/api/v1/teams",
                json={
                    "name": "New Team",
                    "description": "A new team",
                    "monthly_budget": 200.0,
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "t-new"
        assert data["members"] == []

    @pytest.mark.asyncio
    async def test_update_team(self, client):
        """PUT /teams/{id} updates team fields."""
        updated_row = {
            "id": "t-1",
            "name": "Renamed",
            "description": "Infra team",
            "monthly_budget": 2000.0,
            "default_model": "gpt-4o",
            "is_active": True,
            "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2025, 6, 1, tzinfo=timezone.utc),
        }
        conn = _make_async_conn(fetchrow_return=updated_row, fetch_return=[])
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.put(
                "/api/v1/teams/t-1",
                json={"name": "Renamed", "monthly_budget": 2000.0},
            )

        assert resp.status_code == 200
        assert resp.json()["name"] == "Renamed"

    @pytest.mark.asyncio
    async def test_update_team_empty_body(self, client):
        """PUT /teams/{id} with empty body returns 400."""
        conn = _make_async_conn()
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.put("/api/v1/teams/t-1", json={})

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_team(self, client):
        """DELETE /teams/{id} removes team."""
        conn = _make_async_conn(execute_return="DELETE 1")
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.delete("/api/v1/teams/t-1")

        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    @pytest.mark.asyncio
    async def test_delete_team_not_found(self, client):
        """DELETE /teams/{id} returns 404 for missing team."""
        conn = _make_async_conn(execute_return="DELETE 0")
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.delete("/api/v1/teams/t-999")

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_add_team_member(self, client):
        """POST /teams/{id}/members adds member."""
        conn = _make_async_conn()
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.post(
                "/api/v1/teams/t-1/members",
                json={"user_id": "charlie", "role": "member"},
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "added"


# ============================================================================
# Keys Router
# ============================================================================


class TestKeysRouter:
    """Tests for /api/v1/keys endpoints (LiteLLM proxy)."""

    @pytest.mark.asyncio
    async def test_list_keys(self, client):
        """GET /keys proxies to LiteLLM /key/list."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"keys": [{"key": "sk-abc"}]}
        mock_response.raise_for_status = MagicMock()

        http = AsyncMock()
        http.get.return_value = mock_response
        deps.http_client = http

        async with client:
            resp = await client.get("/api/v1/keys")

        assert resp.status_code == 200
        assert "keys" in resp.json()

    @pytest.mark.asyncio
    async def test_generate_key(self, client):
        """POST /keys/generate proxies to LiteLLM /key/generate."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"key": "sk-new-key", "expires": None}
        mock_response.raise_for_status = MagicMock()

        http = AsyncMock()
        http.post.return_value = mock_response
        deps.http_client = http

        async with client:
            resp = await client.post(
                "/api/v1/keys/generate",
                json={"key_alias": "test-key", "max_budget": 100.0},
            )

        assert resp.status_code == 200
        assert resp.json()["key"] == "sk-new-key"

    @pytest.mark.asyncio
    async def test_generate_key_litellm_error(self, client):
        """POST /keys/generate propagates LiteLLM error status."""
        error_response = MagicMock()
        error_response.status_code = 400
        error_response.text = "Bad request from LiteLLM"

        http = AsyncMock()
        http.post.side_effect = httpx.HTTPStatusError(
            message="Bad request",
            request=MagicMock(),
            response=error_response,
        )
        deps.http_client = http

        async with client:
            resp = await client.post(
                "/api/v1/keys/generate",
                json={"key_alias": "bad-key"},
            )

        assert resp.status_code == 400


# ============================================================================
# Settings Router
# ============================================================================


class TestSettingsRouter:
    """Tests for /api/v1/settings endpoints."""

    @pytest.mark.asyncio
    async def test_get_settings(self, client):
        """GET /settings returns settings from DB."""
        rows = [
            {"key": "default_model", "value": "claude-3-5-sonnet"},
            {"key": "enable_caching", "value": "false"},
        ]
        conn = _make_async_conn(fetch_return=rows)
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get("/api/v1/settings")

        assert resp.status_code == 200
        data = resp.json()
        assert data["default_model"] == "claude-3-5-sonnet"
        assert data["enable_caching"] == "false"

    @pytest.mark.asyncio
    async def test_get_settings_no_db(self, client):
        """GET /settings returns defaults when DB pool is None."""
        deps.db_pool = None

        async with client:
            resp = await client.get("/api/v1/settings")

        assert resp.status_code == 200
        data = resp.json()
        # Should be PlatformSettings defaults
        assert data["default_model"] == "gpt-4o-mini"
        assert data["enable_caching"] is True

    @pytest.mark.asyncio
    async def test_update_settings(self, client):
        """PUT /settings writes to DB and returns settings."""
        conn = _make_async_conn()
        deps.db_pool = _make_pool(conn)

        settings_payload = {
            "default_model": "gpt-4o",
            "global_rate_limit": 500,
            "enable_caching": False,
            "cache_ttl_seconds": 1800,
            "enable_cost_tracking": True,
            "enable_budget_enforcement": True,
            "enable_routing_policies": True,
            "maintenance_mode": False,
        }

        async with client:
            resp = await client.put(
                "/api/v1/settings",
                json=settings_payload,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["default_model"] == "gpt-4o"
        assert data["enable_caching"] is False
        # Verify conn.execute was called for each setting key
        assert conn.execute.call_count == len(settings_payload)

    @pytest.mark.asyncio
    async def test_update_settings_no_db(self, client):
        """PUT /settings returns 503 when DB is unavailable."""
        deps.db_pool = None

        async with client:
            resp = await client.put(
                "/api/v1/settings",
                json={"default_model": "gpt-4o"},
            )

        assert resp.status_code == 503


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
