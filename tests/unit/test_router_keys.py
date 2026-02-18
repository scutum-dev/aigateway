"""Unit tests for the Keys router (LiteLLM proxy).

Tests the /api/v1/keys endpoints which proxy to LiteLLM's
/key/generate, /key/list, /key/info, /key/update, and /key/delete endpoints.
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
# Keys Router
# ============================================================================


class TestKeysRouter:
    """Tests for /api/v1/keys endpoints."""

    # ------------------------------------------------------------------
    # POST /api/v1/keys/generate
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_generate_key_success(self, client):
        """POST /keys/generate creates a key via LiteLLM."""
        mock_resp = _mock_http_response(
            200,
            {
                "key": "$TEST_KEY_PLACEHOLDER",
                "key_alias": "test-key",
                "max_budget": 50.0,
            },
        )
        deps.http_client = AsyncMock()
        deps.http_client.post = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.post(
                "/api/v1/keys/generate",
                json={
                    "key_alias": "test-key",
                    "max_budget": 50.0,
                    "models": ["gpt-4o"],
                    "duration": "30d",
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["key"] == "$TEST_KEY_PLACEHOLDER"
        assert data["key_alias"] == "test-key"

    @pytest.mark.asyncio
    async def test_generate_key_litellm_error(self, client):
        """POST /keys/generate propagates LiteLLM errors."""
        mock_resp = _mock_http_response(400, text="Invalid key config")
        deps.http_client = AsyncMock()
        deps.http_client.post = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.post(
                "/api/v1/keys/generate",
                json={"key_alias": "bad-key"},
            )

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_generate_key_no_http_client(self, client):
        """POST /keys/generate returns 503 when http_client is None."""
        deps.http_client = None

        async with client:
            resp = await client.post(
                "/api/v1/keys/generate",
                json={"key_alias": "no-client"},
            )

        assert resp.status_code == 503
        assert "HTTP client not available" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_generate_key_checks_auth_header(self, client):
        """POST /keys/generate sends Authorization header to LiteLLM."""
        mock_resp = _mock_http_response(200, {"key": "sk-new"})
        deps.http_client = AsyncMock()
        deps.http_client.post = AsyncMock(return_value=mock_resp)

        async with client:
            await client.post(
                "/api/v1/keys/generate",
                json={"key_alias": "header-test"},
            )

        call_kwargs = deps.http_client.post.call_args
        headers = call_kwargs.kwargs.get("headers", {})
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")

    # ------------------------------------------------------------------
    # GET /api/v1/keys
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_list_keys_success(self, client):
        """GET /keys returns key list from LiteLLM."""
        mock_resp = _mock_http_response(
            200,
            {
                "keys": [
                    {"key": "sk-key-1", "key_alias": "prod-key"},
                    {"key": "sk-key-2", "key_alias": "dev-key"},
                ]
            },
        )
        deps.http_client = AsyncMock()
        deps.http_client.get = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.get("/api/v1/keys")

        assert resp.status_code == 200
        data = resp.json()
        assert "keys" in data
        assert len(data["keys"]) == 2

    @pytest.mark.asyncio
    async def test_list_keys_litellm_error(self, client):
        """GET /keys propagates LiteLLM errors."""
        mock_resp = _mock_http_response(500, text="Internal Server Error")
        deps.http_client = AsyncMock()
        deps.http_client.get = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.get("/api/v1/keys")

        assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_list_keys_no_http_client(self, client):
        """GET /keys returns 503 when http_client is None."""
        deps.http_client = None

        async with client:
            resp = await client.get("/api/v1/keys")

        assert resp.status_code == 503

    # ------------------------------------------------------------------
    # GET /api/v1/keys/{key}
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_key_info_success(self, client):
        """GET /keys/{key} returns key info from LiteLLM."""
        mock_resp = _mock_http_response(
            200,
            {"key": "sk-key-abc", "key_alias": "my-key", "max_budget": 100.0},
        )
        deps.http_client = AsyncMock()
        deps.http_client.get = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.get("/api/v1/keys/sk-key-abc")

        assert resp.status_code == 200
        assert resp.json()["key"] == "sk-key-abc"

        # Verify key was passed as query parameter
        call_kwargs = deps.http_client.get.call_args
        assert call_kwargs.kwargs["params"]["key"] == "sk-key-abc"

    @pytest.mark.asyncio
    async def test_get_key_info_litellm_error(self, client):
        """GET /keys/{key} propagates LiteLLM errors."""
        mock_resp = _mock_http_response(404, text="Key not found")
        deps.http_client = AsyncMock()
        deps.http_client.get = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.get("/api/v1/keys/nonexistent")

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_key_info_no_http_client(self, client):
        """GET /keys/{key} returns 503 when http_client is None."""
        deps.http_client = None

        async with client:
            resp = await client.get("/api/v1/keys/sk-key-abc")

        assert resp.status_code == 503

    # ------------------------------------------------------------------
    # POST /api/v1/keys/update
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_key_success(self, client):
        """POST /keys/update updates a key via LiteLLM."""
        mock_resp = _mock_http_response(
            200, {"key": "sk-key-1", "max_budget": 200.0}
        )
        deps.http_client = AsyncMock()
        deps.http_client.post = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.post(
                "/api/v1/keys/update",
                json={
                    "key": "sk-key-1",
                    "max_budget": 200.0,
                    "models": ["gpt-4o", "claude-3"],
                },
            )

        assert resp.status_code == 200
        assert resp.json()["max_budget"] == 200.0

    @pytest.mark.asyncio
    async def test_update_key_litellm_error(self, client):
        """POST /keys/update propagates LiteLLM errors."""
        mock_resp = _mock_http_response(400, text="Invalid update")
        deps.http_client = AsyncMock()
        deps.http_client.post = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.post(
                "/api/v1/keys/update",
                json={"key": "sk-key-1", "max_budget": -1},
            )

        assert resp.status_code == 400

    # ------------------------------------------------------------------
    # POST /api/v1/keys/delete
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_key_success(self, client):
        """POST /keys/delete removes key(s) via LiteLLM."""
        mock_resp = _mock_http_response(200, {"status": "deleted"})
        deps.http_client = AsyncMock()
        deps.http_client.post = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.post(
                "/api/v1/keys/delete",
                json={"keys": ["sk-key-1", "sk-key-2"]},
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    @pytest.mark.asyncio
    async def test_delete_key_litellm_error(self, client):
        """POST /keys/delete propagates LiteLLM errors."""
        mock_resp = _mock_http_response(404, text="Key not found")
        deps.http_client = AsyncMock()
        deps.http_client.post = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.post(
                "/api/v1/keys/delete",
                json={"keys": ["nonexistent"]},
            )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_key_no_http_client(self, client):
        """POST /keys/delete returns 503 when http_client is None."""
        deps.http_client = None

        async with client:
            resp = await client.post(
                "/api/v1/keys/delete",
                json={"keys": ["sk-key-1"]},
            )

        assert resp.status_code == 503


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
