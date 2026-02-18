"""Unit tests for the Teams router (LiteLLM proxy).

Tests the /api/v1/teams endpoints which proxy to LiteLLM's
/team/list, /team/new, /team/info, /team/update, /team/delete,
/team/member_add, and /team/member_delete endpoints.
"""

import importlib.util
import os
import sys
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

# ---------------------------------------------------------------------------
# Module loading (mirrors test_admin_routers.py pattern)
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


def _fake_regular_user():
    return UserInfo(user_id="test-user", role="user", is_admin=False)


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
# Teams Router
# ============================================================================


class TestTeamsRouter:
    """Tests for /api/v1/teams endpoints."""

    # ------------------------------------------------------------------
    # GET /api/v1/teams
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_list_teams_success(self, client):
        """GET /teams returns team list from LiteLLM."""
        mock_resp = _mock_http_response(
            200,
            [
                {"team_id": "team-1", "team_alias": "Engineering"},
                {"team_id": "team-2", "team_alias": "Marketing"},
            ],
        )
        deps.http_client = AsyncMock()
        deps.http_client.get = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.get("/api/v1/teams")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["team_alias"] == "Engineering"

    @pytest.mark.asyncio
    async def test_list_teams_no_http_client(self, client):
        """GET /teams returns 503 when http_client is None."""
        deps.http_client = None

        async with client:
            resp = await client.get("/api/v1/teams")

        assert resp.status_code == 503
        assert "HTTP client not available" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_teams_litellm_error(self, client):
        """GET /teams propagates LiteLLM errors."""
        mock_resp = _mock_http_response(500, text="Internal Server Error")
        deps.http_client = AsyncMock()
        deps.http_client.get = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.get("/api/v1/teams")

        assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_list_teams_checks_auth_header(self, client):
        """GET /teams sends Authorization header to LiteLLM."""
        mock_resp = _mock_http_response(200, [])
        deps.http_client = AsyncMock()
        deps.http_client.get = AsyncMock(return_value=mock_resp)

        async with client:
            await client.get("/api/v1/teams")

        call_kwargs = deps.http_client.get.call_args
        headers = call_kwargs.kwargs.get("headers", {})
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")

    # ------------------------------------------------------------------
    # POST /api/v1/teams
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_team_success(self, client):
        """POST /teams creates a team via LiteLLM."""
        mock_resp = _mock_http_response(200, {"team_id": "new-team-1", "team_alias": "Data Science"})
        deps.http_client = AsyncMock()
        deps.http_client.post = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.post(
                "/api/v1/teams",
                json={
                    "team_alias": "Data Science",
                    "max_budget": 100.0,
                    "models": ["gpt-4o", "claude-3"],
                },
            )

        assert resp.status_code == 200
        assert resp.json()["team_alias"] == "Data Science"

    @pytest.mark.asyncio
    async def test_create_team_litellm_error(self, client):
        """POST /teams propagates LiteLLM errors."""
        mock_resp = _mock_http_response(400, text="Invalid team config")
        deps.http_client = AsyncMock()
        deps.http_client.post = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.post(
                "/api/v1/teams",
                json={"team_alias": "Bad Team"},
            )

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_create_team_no_http_client(self, client):
        """POST /teams returns 503 when http_client is None."""
        deps.http_client = None

        async with client:
            resp = await client.post(
                "/api/v1/teams",
                json={"team_alias": "No Client"},
            )

        assert resp.status_code == 503

    # ------------------------------------------------------------------
    # GET /api/v1/teams/{team_id}
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_team_success(self, client):
        """GET /teams/{team_id} returns team info from LiteLLM."""
        mock_resp = _mock_http_response(200, {"team_id": "team-abc", "team_alias": "Platform"})
        deps.http_client = AsyncMock()
        deps.http_client.get = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.get("/api/v1/teams/team-abc")

        assert resp.status_code == 200
        assert resp.json()["team_id"] == "team-abc"

        # Verify team_id was passed as query parameter
        call_kwargs = deps.http_client.get.call_args
        assert call_kwargs.kwargs["params"]["team_id"] == "team-abc"

    @pytest.mark.asyncio
    async def test_get_team_litellm_error(self, client):
        """GET /teams/{team_id} propagates LiteLLM errors."""
        mock_resp = _mock_http_response(404, text="Team not found")
        deps.http_client = AsyncMock()
        deps.http_client.get = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.get("/api/v1/teams/nonexistent")

        assert resp.status_code == 404

    # ------------------------------------------------------------------
    # POST /api/v1/teams/update
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_team_success(self, client):
        """POST /teams/update updates a team via LiteLLM."""
        mock_resp = _mock_http_response(200, {"team_id": "team-1", "team_alias": "Updated Team"})
        deps.http_client = AsyncMock()
        deps.http_client.post = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.post(
                "/api/v1/teams/update",
                json={
                    "team_id": "team-1",
                    "team_alias": "Updated Team",
                    "max_budget": 500.0,
                },
            )

        assert resp.status_code == 200
        assert resp.json()["team_alias"] == "Updated Team"

    @pytest.mark.asyncio
    async def test_update_team_litellm_error(self, client):
        """POST /teams/update propagates LiteLLM errors."""
        mock_resp = _mock_http_response(400, text="Invalid update")
        deps.http_client = AsyncMock()
        deps.http_client.post = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.post(
                "/api/v1/teams/update",
                json={"team_id": "team-1", "team_alias": "Bad Update"},
            )

        assert resp.status_code == 400

    # ------------------------------------------------------------------
    # POST /api/v1/teams/delete
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_team_success(self, client):
        """POST /teams/delete removes team(s) via LiteLLM."""
        mock_resp = _mock_http_response(200, {"status": "deleted"})
        deps.http_client = AsyncMock()
        deps.http_client.post = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.post(
                "/api/v1/teams/delete",
                json={"team_ids": ["team-1", "team-2"]},
            )

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_team_litellm_error(self, client):
        """POST /teams/delete propagates LiteLLM errors."""
        mock_resp = _mock_http_response(404, text="Team not found")
        deps.http_client = AsyncMock()
        deps.http_client.post = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.post(
                "/api/v1/teams/delete",
                json={"team_ids": ["nonexistent"]},
            )

        assert resp.status_code == 404

    # ------------------------------------------------------------------
    # POST /api/v1/teams/{team_id}/members
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_add_member_success(self, client):
        """POST /teams/{team_id}/members adds a member via LiteLLM."""
        mock_resp = _mock_http_response(200, {"team_id": "team-1", "members": [{"user_id": "user-1", "role": "user"}]})
        deps.http_client = AsyncMock()
        deps.http_client.post = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.post(
                "/api/v1/teams/team-1/members",
                json={"member": {"role": "user", "user_id": "user-1"}},
            )

        assert resp.status_code == 200

        # Verify the correct payload was sent to LiteLLM
        call_kwargs = deps.http_client.post.call_args
        body = call_kwargs.kwargs["json"]
        assert body["team_id"] == "team-1"
        assert body["member"]["user_id"] == "user-1"

    @pytest.mark.asyncio
    async def test_add_member_litellm_error(self, client):
        """POST /teams/{team_id}/members propagates LiteLLM errors."""
        mock_resp = _mock_http_response(400, text="Invalid member")
        deps.http_client = AsyncMock()
        deps.http_client.post = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.post(
                "/api/v1/teams/team-1/members",
                json={"member": {"role": "invalid"}},
            )

        assert resp.status_code == 400

    # ------------------------------------------------------------------
    # POST /api/v1/teams/{team_id}/members/delete
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_member_success(self, client):
        """POST /teams/{team_id}/members/delete removes a member via LiteLLM."""
        mock_resp = _mock_http_response(200, {"status": "member_deleted"})
        deps.http_client = AsyncMock()
        deps.http_client.post = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.post(
                "/api/v1/teams/team-1/members/delete",
                json={"user_id": "user-1"},
            )

        assert resp.status_code == 200

        # Verify the correct payload was sent to LiteLLM
        call_kwargs = deps.http_client.post.call_args
        body = call_kwargs.kwargs["json"]
        assert body["team_id"] == "team-1"
        assert body["user_id"] == "user-1"

    @pytest.mark.asyncio
    async def test_delete_member_litellm_error(self, client):
        """POST /teams/{team_id}/members/delete propagates LiteLLM errors."""
        mock_resp = _mock_http_response(404, text="Member not found")
        deps.http_client = AsyncMock()
        deps.http_client.post = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.post(
                "/api/v1/teams/team-1/members/delete",
                json={"user_id": "nonexistent"},
            )

        assert resp.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
