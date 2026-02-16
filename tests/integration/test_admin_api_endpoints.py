"""Integration tests for the Admin API endpoints.

Tests HTTP endpoints, JWT auth, middleware stack, and CRUD operations
with mocked database and HTTP clients.
"""

import sys
import os
import importlib.util
import time
import json
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from datetime import datetime, timezone

import pytest
import httpx

# Load the admin-api module
_service_dir = os.path.join(os.path.dirname(__file__), "../../src/admin-api")
sys.path.insert(0, _service_dir)
_spec = importlib.util.spec_from_file_location(
    "admin_api_integ", os.path.join(_service_dir, "main.py")
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["admin_api_integ"] = _mod
_spec.loader.exec_module(_mod)

app = _mod.app

# Load auth module for token creation
_auth_spec = importlib.util.spec_from_file_location(
    "admin_api_auth", os.path.join(_service_dir, "auth.py")
)
_auth_mod = importlib.util.module_from_spec(_auth_spec)
_auth_spec.loader.exec_module(_auth_mod)


def _auth_headers():
    """Create JWT auth headers for an admin user."""
    token, _ = _auth_mod.create_access_token(
        {"user_id": "admin", "role": "admin", "is_admin": True}
    )
    return {"Authorization": f"Bearer {token}"}


def _user_headers():
    """Create JWT auth headers for a non-admin user."""
    token, _ = _auth_mod.create_access_token(
        {"user_id": "user-1", "role": "user", "is_admin": False}
    )
    return {"Authorization": f"Bearer {token}"}


def _mock_db_pool():
    """Build a mock asyncpg pool with async context manager."""
    pool = MagicMock()
    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = ctx
    return pool, conn


@pytest.fixture(autouse=True)
def _reset_state():
    """Reset module state between tests."""
    original_db = _mod.db_pool
    original_http = _mod.http_client
    original_redis = _mod.redis_client
    original_shutdown = _mod.shutdown_event
    original_active = _mod.active_requests
    original_rate_cache = _mod._rate_limit_cache.copy()
    original_inmemory = _mod._inmemory_requests[:]
    yield
    _mod.db_pool = original_db
    _mod.http_client = original_http
    _mod.redis_client = original_redis
    _mod.shutdown_event = original_shutdown
    _mod.active_requests = original_active
    _mod._rate_limit_cache.update(original_rate_cache)
    _mod._inmemory_requests[:] = original_inmemory


@pytest.fixture
def client():
    """ASGI test client with no external dependencies."""
    _mod.INTERNAL_SERVICE_KEY = ""
    _mod.db_pool = None
    _mod.http_client = AsyncMock()
    _mod.redis_client = None
    _mod.shutdown_event = None
    _mod.active_requests = 0
    _mod._rate_limit_cache.update({"value": None, "expires_at": 0.0})
    _mod._inmemory_requests.clear()
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# ============================================================================
# Health & Auth
# ============================================================================


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        """Health endpoint should return 200."""
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


class TestAuthLogin:
    @pytest.mark.asyncio
    async def test_login_invalid_key(self, client):
        """Login with invalid key should return 401."""
        with patch.object(_auth_mod, "validate_api_key", new_callable=AsyncMock, return_value=None):
            with patch("auth.validate_api_key", new_callable=AsyncMock, return_value=None):
                resp = await client.post("/auth/login", json={"api_key": "bad-key"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_valid_admin_key(self, client):
        """Login with valid admin key should return access token."""
        mock_info = {"user_id": "admin", "role": "admin", "is_admin": True}
        with patch("auth.validate_api_key", new_callable=AsyncMock, return_value=mock_info):
            resp = await client.post("/auth/login", json={"api_key": "sk-master"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"


class TestAuthMe:
    @pytest.mark.asyncio
    async def test_me_without_token(self, client):
        """GET /auth/me without token should return 401 or 403."""
        resp = await client.get("/auth/me")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_me_with_valid_token(self, client):
        """GET /auth/me with valid token should return user info."""
        resp = await client.get("/auth/me", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "admin"
        assert data["is_admin"] is True


# ============================================================================
# Middleware
# ============================================================================


class TestRateLimitMiddleware:
    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self, client):
        """Requests past the rate limit should return 429."""
        _mod._rate_limit_cache.update({"value": 2, "expires_at": time.time() + 60})
        _mod._inmemory_requests.clear()
        _mod.redis_client = None

        headers = _auth_headers()
        # First two requests should pass (count 1 and 2 are within limit)
        resp1 = await client.get("/api/v1/settings", headers=headers)
        resp2 = await client.get("/api/v1/settings", headers=headers)
        # Third request exceeds the limit (count > 2)
        resp3 = await client.get("/api/v1/settings", headers=headers)
        assert resp3.status_code == 429
        assert "Rate limit" in resp3.json()["detail"]


class TestCORSMiddleware:
    @pytest.mark.asyncio
    async def test_cors_preflight(self, client):
        """OPTIONS request should include CORS headers."""
        resp = await client.options(
            "/api/v1/models",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization",
            },
        )
        assert resp.status_code == 200
        assert "access-control-allow-origin" in resp.headers


class TestRequestSizeLimitMiddleware:
    @pytest.mark.asyncio
    async def test_oversized_request(self, client):
        """Request exceeding MAX_REQUEST_SIZE should return 413."""
        huge_size = _mod.MAX_REQUEST_SIZE + 1
        resp = await client.post(
            "/auth/login",
            content=b"x",
            headers={"Content-Length": str(huge_size), "Content-Type": "application/json"},
        )
        assert resp.status_code == 413


# ============================================================================
# Model CRUD
# ============================================================================


class TestModelEndpoints:
    @pytest.mark.asyncio
    async def test_list_models_no_auth(self, client):
        """GET /api/v1/models without auth should return 403."""
        resp = await client.get("/api/v1/models")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_list_models_no_db(self, client):
        """GET /api/v1/models with auth but no DB should return 503."""
        _mod.db_pool = None
        resp = await client.get("/api/v1/models", headers=_auth_headers())
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_list_models_success(self, client):
        """GET /api/v1/models with auth and DB should return models."""
        pool, conn = _mock_db_pool()
        now = datetime.now(timezone.utc)
        conn.fetch.return_value = [
            {
                "model_id": "gpt-4o",
                "provider": "openai",
                "tier": "premium",
                "cost_per_1k_input": Decimal("0.0025"),
                "cost_per_1k_output": Decimal("0.01"),
                "supports_streaming": True,
                "supports_function_calling": True,
                "supports_vision": False,
                "default_latency_sla_ms": 5000,
                "is_active": True,
                "updated_at": now,
            }
        ]
        _mod.db_pool = pool
        resp = await client.get("/api/v1/models", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["model_id"] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_update_model_success(self, client):
        """PUT /api/v1/models/{id} with valid update should return 200."""
        pool, conn = _mock_db_pool()
        conn.fetchrow.return_value = {
            "model_id": "gpt-4o",
            "provider": "openai",
            "tier": "economy",
            "cost_per_1k_input": Decimal("0.0025"),
            "cost_per_1k_output": Decimal("0.01"),
            "supports_streaming": True,
            "supports_function_calling": True,
            "supports_vision": False,
            "default_latency_sla_ms": 5000,
            "is_active": True,
            "updated_at": datetime.now(timezone.utc),
        }
        _mod.db_pool = pool
        resp = await client.put(
            "/api/v1/models/gpt-4o",
            json={"tier": "economy"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["tier"] == "economy"

    @pytest.mark.asyncio
    async def test_update_model_no_updates(self, client):
        """PUT /api/v1/models/{id} with empty body should return 400."""
        pool, conn = _mock_db_pool()
        _mod.db_pool = pool
        resp = await client.put(
            "/api/v1/models/gpt-4o",
            json={},
            headers=_auth_headers(),
        )
        assert resp.status_code == 400


# ============================================================================
# Budget CRUD
# ============================================================================


class TestBudgetEndpoints:
    def _budget_row(self):
        """Return a mock budget database row."""
        now = datetime.now(timezone.utc)
        return {
            "id": "b-1",
            "name": "Engineering",
            "entity_type": "team",
            "entity_id": "team-eng",
            "monthly_limit": Decimal("500.00"),
            "current_spend": Decimal("123.45"),
            "soft_limit_percent": Decimal("0.8"),
            "hard_limit_percent": Decimal("1.0"),
            "alert_email": "eng@example.com",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }

    @pytest.mark.asyncio
    async def test_list_budgets_success(self, client):
        """GET /api/v1/budgets with auth and DB should return budgets."""
        pool, conn = _mock_db_pool()
        conn.fetch.return_value = [self._budget_row()]
        _mod.db_pool = pool
        resp = await client.get("/api/v1/budgets", headers=_auth_headers())
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    @pytest.mark.asyncio
    async def test_create_budget_success(self, client):
        """POST /api/v1/budgets should create a budget."""
        pool, conn = _mock_db_pool()
        conn.fetchrow.return_value = self._budget_row()
        _mod.db_pool = pool
        resp = await client.post(
            "/api/v1/budgets",
            json={
                "name": "Engineering",
                "entity_type": "team",
                "entity_id": "team-eng",
                "monthly_limit": 500.0,
            },
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Engineering"

    @pytest.mark.asyncio
    async def test_list_budgets_no_db(self, client):
        """GET /api/v1/budgets without DB should return 503."""
        _mod.db_pool = None
        resp = await client.get("/api/v1/budgets", headers=_auth_headers())
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_update_budget_not_found(self, client):
        """PUT /api/v1/budgets/{id} for missing budget should return 404."""
        pool, conn = _mock_db_pool()
        conn.fetchrow.return_value = None
        _mod.db_pool = pool
        resp = await client.put(
            "/api/v1/budgets/nonexistent",
            json={"monthly_limit": 1000.0},
            headers=_auth_headers(),
        )
        assert resp.status_code == 404


# ============================================================================
# Team CRUD
# ============================================================================


class TestTeamEndpoints:
    def _team_row(self):
        """Return a mock team database row."""
        return {
            "id": "t-1",
            "name": "Platform",
            "description": "Platform team",
            "monthly_budget": Decimal("1000.0"),
            "default_model": "gpt-4o",
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

    @pytest.mark.asyncio
    async def test_list_teams_success(self, client):
        """GET /api/v1/teams with auth and DB should return teams."""
        pool, conn = _mock_db_pool()
        conn.fetch.side_effect = [
            [self._team_row()],
            [{"user_id": "user-1"}, {"user_id": "user-2"}],
        ]
        _mod.db_pool = pool
        resp = await client.get("/api/v1/teams", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert "user-1" in data[0]["members"]

    @pytest.mark.asyncio
    async def test_create_team_success(self, client):
        """POST /api/v1/teams should create a team."""
        pool, conn = _mock_db_pool()
        conn.fetchrow.return_value = self._team_row()
        _mod.db_pool = pool
        resp = await client.post(
            "/api/v1/teams",
            json={"name": "Platform", "description": "Platform team"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Platform"

    @pytest.mark.asyncio
    async def test_update_team_success(self, client):
        """PUT /api/v1/teams/{id} should update a team."""
        pool, conn = _mock_db_pool()
        conn.fetchrow.return_value = self._team_row()
        conn.fetch.return_value = []  # no members
        _mod.db_pool = pool
        resp = await client.put(
            "/api/v1/teams/t-1",
            json={"name": "Platform-v2"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_update_team_empty_body(self, client):
        """PUT /api/v1/teams/{id} with no fields returns 400."""
        pool, conn = _mock_db_pool()
        _mod.db_pool = pool
        resp = await client.put(
            "/api/v1/teams/t-1",
            json={},
            headers=_auth_headers(),
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_team_success(self, client):
        """DELETE /api/v1/teams/{id} should delete a team."""
        pool, conn = _mock_db_pool()
        conn.execute.return_value = "DELETE 1"
        _mod.db_pool = pool
        resp = await client.delete(
            "/api/v1/teams/t-1",
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    @pytest.mark.asyncio
    async def test_delete_team_not_found(self, client):
        """DELETE /api/v1/teams/{id} returns 404 for unknown team."""
        pool, conn = _mock_db_pool()
        conn.execute.return_value = "DELETE 0"
        _mod.db_pool = pool
        resp = await client.delete(
            "/api/v1/teams/t-999",
            headers=_auth_headers(),
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_add_team_member_success(self, client):
        """POST /api/v1/teams/{id}/members should add a member."""
        pool, conn = _mock_db_pool()
        conn.execute.return_value = "INSERT 0 1"
        _mod.db_pool = pool
        resp = await client.post(
            "/api/v1/teams/t-1/members",
            json={"user_id": "user-3", "role": "member"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "added"


# ============================================================================
# MCP Server CRUD
# ============================================================================


class TestMCPServerEndpoints:
    def _mcp_row(self):
        """Return a mock MCP server database row."""
        return {
            "id": "mcp-1",
            "name": "filesystem",
            "server_type": "stdio",
            "command": "npx",
            "url": None,
            "args": ["-y", "@modelcontextprotocol/server-filesystem"],
            "env": json.dumps({"HOME": "/tmp"}),
            "tools": ["read_file", "write_file"],
            "is_active": True,
        }

    @pytest.mark.asyncio
    async def test_list_mcp_servers_success(self, client):
        """GET /api/v1/mcp-servers should return servers."""
        pool, conn = _mock_db_pool()
        conn.fetch.return_value = [self._mcp_row()]
        _mod.db_pool = pool
        resp = await client.get("/api/v1/mcp-servers", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "filesystem"

    @pytest.mark.asyncio
    async def test_create_mcp_server_success(self, client):
        """POST /api/v1/mcp-servers should create a server config."""
        pool, conn = _mock_db_pool()
        conn.fetchrow.return_value = self._mcp_row()
        _mod.db_pool = pool
        resp = await client.post(
            "/api/v1/mcp-servers",
            json={
                "name": "filesystem",
                "server_type": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem"],
            },
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["server_type"] == "stdio"

    @pytest.mark.asyncio
    async def test_preview_gateway_config(self, client):
        """GET /api/v1/mcp-servers/sync/preview should return config YAML."""
        pool, conn = _mock_db_pool()
        conn.fetch.return_value = [self._mcp_row()]
        _mod.db_pool = pool
        resp = await client.get(
            "/api/v1/mcp-servers/sync/preview", headers=_auth_headers()
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "config_yaml" in data
        assert data["active_servers"] == 1

    @pytest.mark.asyncio
    async def test_delete_mcp_server_not_found(self, client):
        """DELETE /api/v1/mcp-servers/{id} for missing server should return 404."""
        pool, conn = _mock_db_pool()
        conn.execute.return_value = "DELETE 0"
        _mod.db_pool = pool
        resp = await client.delete(
            "/api/v1/mcp-servers/nonexistent", headers=_auth_headers()
        )
        assert resp.status_code == 404


# ============================================================================
# Workflow Proxy
# ============================================================================


class TestWorkflowEndpoints:
    @pytest.mark.asyncio
    async def test_execute_workflow_proxies(self, client):
        """POST /api/v1/workflow-executions should proxy to workflow engine."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"execution_id": "exec-1", "status": "running"}
        mock_resp.raise_for_status = MagicMock()
        _mod.http_client.post.return_value = mock_resp

        resp = await client.post(
            "/api/v1/workflow-executions",
            json={
                "template_type": "research",
                "input_text": "test query",
            },
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["execution_id"] == "exec-1"

    @pytest.mark.asyncio
    async def test_list_workflow_executions_proxies(self, client):
        """GET /api/v1/workflow-executions should proxy to workflow engine."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []
        mock_resp.raise_for_status = MagicMock()
        _mod.http_client.get.return_value = mock_resp

        resp = await client.get(
            "/api/v1/workflow-executions", headers=_auth_headers()
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_workflow_templates_proxies(self, client):
        """GET /api/v1/workflow-templates should proxy to workflow engine."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"name": "research", "description": "Deep research"}]
        mock_resp.raise_for_status = MagicMock()
        _mod.http_client.get.return_value = mock_resp

        resp = await client.get(
            "/api/v1/workflow-templates", headers=_auth_headers()
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1


# ============================================================================
# Settings
# ============================================================================


class TestSettingsEndpoints:
    @pytest.mark.asyncio
    async def test_get_settings_no_db_returns_defaults(self, client):
        """GET /api/v1/settings without DB should return defaults."""
        _mod.db_pool = None
        resp = await client.get("/api/v1/settings", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert data["default_model"] == "gpt-4o-mini"
        assert data["global_rate_limit"] == 1000

    @pytest.mark.asyncio
    async def test_get_settings_with_db(self, client):
        """GET /api/v1/settings with DB should return stored settings."""
        pool, conn = _mock_db_pool()
        conn.fetch.return_value = [
            {"key": "default_model", "value": "claude-3-opus"},
            {"key": "maintenance_mode", "value": "true"},
        ]
        _mod.db_pool = pool
        resp = await client.get("/api/v1/settings", headers=_auth_headers())
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_update_settings_success(self, client):
        """PUT /api/v1/settings with admin auth should update settings."""
        pool, conn = _mock_db_pool()
        conn.execute.return_value = "INSERT 0 1"
        _mod.db_pool = pool
        resp = await client.put(
            "/api/v1/settings",
            json={
                "default_model": "claude-3-opus",
                "global_rate_limit": 500,
                "enable_caching": True,
                "cache_ttl_seconds": 1800,
                "enable_cost_tracking": True,
                "enable_budget_enforcement": True,
                "enable_routing_policies": True,
                "maintenance_mode": False,
            },
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["default_model"] == "claude-3-opus"
