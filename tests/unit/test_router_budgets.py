"""Unit tests for the Budgets router (LiteLLM proxy).

Tests the /api/v1/budgets endpoints which proxy to LiteLLM's
/budget/list, /budget/new, /budget/info, /budget/update, and /budget/delete endpoints.
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
# Budgets Router
# ============================================================================


class TestBudgetsRouter:
    """Tests for /api/v1/budgets endpoints."""

    # ------------------------------------------------------------------
    # GET /api/v1/budgets
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_list_budgets_success(self, client):
        """GET /budgets returns budget list from LiteLLM."""
        mock_resp = _mock_http_response(
            200,
            [
                {"budget_id": "b1", "max_budget": 100.0},
                {"budget_id": "b2", "max_budget": 500.0},
            ],
        )
        deps.http_client = AsyncMock()
        deps.http_client.get = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.get("/api/v1/budgets")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["budget_id"] == "b1"

    @pytest.mark.asyncio
    async def test_list_budgets_litellm_error(self, client):
        """GET /budgets propagates LiteLLM errors."""
        mock_resp = _mock_http_response(500, text="Internal Server Error")
        deps.http_client = AsyncMock()
        deps.http_client.get = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.get("/api/v1/budgets")

        assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_list_budgets_no_http_client(self, client):
        """GET /budgets returns 503 when http_client is None."""
        deps.http_client = None

        async with client:
            resp = await client.get("/api/v1/budgets")

        assert resp.status_code == 503
        assert "HTTP client not available" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_budgets_checks_auth_header(self, client):
        """GET /budgets sends Authorization header to LiteLLM."""
        mock_resp = _mock_http_response(200, [])
        deps.http_client = AsyncMock()
        deps.http_client.get = AsyncMock(return_value=mock_resp)

        async with client:
            await client.get("/api/v1/budgets")

        call_kwargs = deps.http_client.get.call_args
        headers = call_kwargs.kwargs.get("headers", {})
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")

    # ------------------------------------------------------------------
    # POST /api/v1/budgets
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_budget_success(self, client):
        """POST /budgets creates a budget via LiteLLM."""
        mock_resp = _mock_http_response(
            200,
            {"budget_id": "new-budget-1", "max_budget": 250.0, "soft_budget": 200.0},
        )
        deps.http_client = AsyncMock()
        deps.http_client.post = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.post(
                "/api/v1/budgets",
                json={
                    "max_budget": 250.0,
                    "soft_budget": 200.0,
                    "rpm_limit": 100,
                    "tpm_limit": 50000,
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["budget_id"] == "new-budget-1"
        assert data["max_budget"] == 250.0

    @pytest.mark.asyncio
    async def test_create_budget_litellm_error(self, client):
        """POST /budgets propagates LiteLLM errors."""
        mock_resp = _mock_http_response(400, text="Invalid budget config")
        deps.http_client = AsyncMock()
        deps.http_client.post = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.post(
                "/api/v1/budgets",
                json={"max_budget": -1.0},
            )

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_create_budget_no_http_client(self, client):
        """POST /budgets returns 503 when http_client is None."""
        deps.http_client = None

        async with client:
            resp = await client.post(
                "/api/v1/budgets",
                json={"max_budget": 100.0},
            )

        assert resp.status_code == 503

    # ------------------------------------------------------------------
    # GET /api/v1/budgets/{budget_id}
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_budget_success(self, client):
        """GET /budgets/{budget_id} returns budget info from LiteLLM."""
        mock_resp = _mock_http_response(
            200,
            {"budget_id": "budget-abc", "max_budget": 500.0, "spend": 123.45},
        )
        deps.http_client = AsyncMock()
        deps.http_client.get = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.get("/api/v1/budgets/budget-abc")

        assert resp.status_code == 200
        assert resp.json()["budget_id"] == "budget-abc"

        # Verify budget_id was passed as query parameter
        call_kwargs = deps.http_client.get.call_args
        assert call_kwargs.kwargs["params"]["budgets"] == "budget-abc"

    @pytest.mark.asyncio
    async def test_get_budget_litellm_error(self, client):
        """GET /budgets/{budget_id} propagates LiteLLM errors."""
        mock_resp = _mock_http_response(404, text="Budget not found")
        deps.http_client = AsyncMock()
        deps.http_client.get = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.get("/api/v1/budgets/nonexistent")

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_budget_no_http_client(self, client):
        """GET /budgets/{budget_id} returns 503 when http_client is None."""
        deps.http_client = None

        async with client:
            resp = await client.get("/api/v1/budgets/budget-abc")

        assert resp.status_code == 503

    # ------------------------------------------------------------------
    # POST /api/v1/budgets/update
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_budget_success(self, client):
        """POST /budgets/update updates a budget via LiteLLM."""
        mock_resp = _mock_http_response(
            200, {"budget_id": "b1", "max_budget": 1000.0}
        )
        deps.http_client = AsyncMock()
        deps.http_client.post = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.post(
                "/api/v1/budgets/update",
                json={
                    "budget_id": "b1",
                    "max_budget": 1000.0,
                    "soft_budget": 800.0,
                },
            )

        assert resp.status_code == 200
        assert resp.json()["max_budget"] == 1000.0

    @pytest.mark.asyncio
    async def test_update_budget_litellm_error(self, client):
        """POST /budgets/update propagates LiteLLM errors."""
        mock_resp = _mock_http_response(400, text="Invalid budget update")
        deps.http_client = AsyncMock()
        deps.http_client.post = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.post(
                "/api/v1/budgets/update",
                json={"budget_id": "b1", "max_budget": -500.0},
            )

        assert resp.status_code == 400

    # ------------------------------------------------------------------
    # POST /api/v1/budgets/delete
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_budget_success(self, client):
        """POST /budgets/delete removes a budget via LiteLLM."""
        mock_resp = _mock_http_response(200, {"status": "deleted"})
        deps.http_client = AsyncMock()
        deps.http_client.post = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.post(
                "/api/v1/budgets/delete",
                json={"id": "budget-abc"},
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    @pytest.mark.asyncio
    async def test_delete_budget_litellm_error(self, client):
        """POST /budgets/delete propagates LiteLLM errors."""
        mock_resp = _mock_http_response(404, text="Budget not found")
        deps.http_client = AsyncMock()
        deps.http_client.post = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.post(
                "/api/v1/budgets/delete",
                json={"id": "nonexistent"},
            )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_budget_no_http_client(self, client):
        """POST /budgets/delete returns 503 when http_client is None."""
        deps.http_client = None

        async with client:
            resp = await client.post(
                "/api/v1/budgets/delete",
                json={"id": "budget-abc"},
            )

        assert resp.status_code == 503


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
