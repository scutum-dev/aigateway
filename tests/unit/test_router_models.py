"""Unit tests for the Models router (LiteLLM proxy).

Tests the /api/v1/models endpoints which proxy to LiteLLM's
/model/info, /model/new, and /model/delete endpoints.
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
# Models Router
# ============================================================================


class TestModelsRouter:
    """Tests for /api/v1/models endpoints."""

    # ------------------------------------------------------------------
    # GET /api/v1/models
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_list_models_success(self, client):
        """GET /models returns model data from LiteLLM."""
        mock_resp = _mock_http_response(
            200,
            {"data": [{"model_name": "gpt-4o", "model_info": {"id": "m1"}}]},
        )
        deps.http_client = AsyncMock()
        deps.http_client.get = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.get("/api/v1/models")

        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert data["data"][0]["model_name"] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_list_models_litellm_error(self, client):
        """GET /models returns error when LiteLLM returns 500."""
        mock_resp = _mock_http_response(500, text="Internal Server Error")
        deps.http_client = AsyncMock()
        deps.http_client.get = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.get("/api/v1/models")

        assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_list_models_no_http_client(self, client):
        """GET /models returns 503 when http_client is None."""
        deps.http_client = None

        async with client:
            resp = await client.get("/api/v1/models")

        assert resp.status_code == 503
        assert "HTTP client not available" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_models_checks_auth_header(self, client):
        """GET /models sends Authorization header to LiteLLM."""
        mock_resp = _mock_http_response(200, {"data": []})
        deps.http_client = AsyncMock()
        deps.http_client.get = AsyncMock(return_value=mock_resp)

        async with client:
            await client.get("/api/v1/models")

        call_kwargs = deps.http_client.get.call_args
        headers = call_kwargs.kwargs.get("headers", {})
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")

    @pytest.mark.asyncio
    async def test_list_models_litellm_400(self, client):
        """GET /models forwards 400-level errors from LiteLLM."""
        mock_resp = _mock_http_response(400, text="Bad Request")
        deps.http_client = AsyncMock()
        deps.http_client.get = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.get("/api/v1/models")

        assert resp.status_code == 400

    # ------------------------------------------------------------------
    # GET /api/v1/models/{model_id}
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_model_found_by_id(self, client):
        """GET /models/{model_id} returns model matched by model_info.id."""
        mock_resp = _mock_http_response(
            200,
            {
                "data": [
                    {"model_name": "gpt-4o", "model_info": {"id": "abc-123"}},
                    {"model_name": "claude-3", "model_info": {"id": "def-456"}},
                ]
            },
        )
        deps.http_client = AsyncMock()
        deps.http_client.get = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.get("/api/v1/models/abc-123")

        assert resp.status_code == 200
        assert resp.json()["model_name"] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_get_model_found_by_name(self, client):
        """GET /models/{model_id} matches by model_name as fallback."""
        mock_resp = _mock_http_response(
            200,
            {
                "data": [
                    {"model_name": "gpt-4o", "model_info": {"id": "m1"}},
                    {"model_name": "claude-3", "model_info": {"id": "m2"}},
                ]
            },
        )
        deps.http_client = AsyncMock()
        deps.http_client.get = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.get("/api/v1/models/claude-3")

        assert resp.status_code == 200
        assert resp.json()["model_name"] == "claude-3"

    @pytest.mark.asyncio
    async def test_get_model_not_found(self, client):
        """GET /models/{model_id} returns 404 when model not in list."""
        mock_resp = _mock_http_response(
            200,
            {"data": [{"model_name": "gpt-4o", "model_info": {"id": "m1"}}]},
        )
        deps.http_client = AsyncMock()
        deps.http_client.get = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.get("/api/v1/models/nonexistent")

        assert resp.status_code == 404
        assert "Model not found" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_model_litellm_error(self, client):
        """GET /models/{model_id} propagates LiteLLM errors."""
        mock_resp = _mock_http_response(502, text="Bad Gateway")
        deps.http_client = AsyncMock()
        deps.http_client.get = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.get("/api/v1/models/some-model")

        assert resp.status_code == 502

    @pytest.mark.asyncio
    async def test_get_model_no_http_client(self, client):
        """GET /models/{model_id} returns 503 when http_client is None."""
        deps.http_client = None

        async with client:
            resp = await client.get("/api/v1/models/some-model")

        assert resp.status_code == 503

    # ------------------------------------------------------------------
    # POST /api/v1/models
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_model_success(self, client):
        """POST /models creates a model via LiteLLM."""
        mock_resp = _mock_http_response(
            200, {"model_name": "new-model", "status": "created"}
        )
        deps.http_client = AsyncMock()
        deps.http_client.post = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.post(
                "/api/v1/models",
                json={
                    "model_name": "new-model",
                    "litellm_params": {"model": "gpt-4o", "api_key": "sk-test"},
                },
            )

        assert resp.status_code == 200
        assert resp.json()["model_name"] == "new-model"

    @pytest.mark.asyncio
    async def test_create_model_litellm_error(self, client):
        """POST /models propagates LiteLLM errors."""
        mock_resp = _mock_http_response(400, text="Invalid model config")
        deps.http_client = AsyncMock()
        deps.http_client.post = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.post(
                "/api/v1/models",
                json={
                    "model_name": "bad-model",
                    "litellm_params": {"model": "invalid"},
                },
            )

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_create_model_no_http_client(self, client):
        """POST /models returns 503 when http_client is None."""
        deps.http_client = None

        async with client:
            resp = await client.post(
                "/api/v1/models",
                json={
                    "model_name": "new-model",
                    "litellm_params": {"model": "gpt-4o"},
                },
            )

        assert resp.status_code == 503

    # ------------------------------------------------------------------
    # POST /api/v1/models/delete
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_model_success(self, client):
        """POST /models/delete removes a model via LiteLLM."""
        mock_resp = _mock_http_response(200, {"status": "deleted"})
        deps.http_client = AsyncMock()
        deps.http_client.post = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.post(
                "/api/v1/models/delete",
                json={"id": "model-abc-123"},
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    @pytest.mark.asyncio
    async def test_delete_model_litellm_error(self, client):
        """POST /models/delete propagates LiteLLM errors."""
        mock_resp = _mock_http_response(404, text="Model not found")
        deps.http_client = AsyncMock()
        deps.http_client.post = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.post(
                "/api/v1/models/delete",
                json={"id": "nonexistent"},
            )

        assert resp.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
