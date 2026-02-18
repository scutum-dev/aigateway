"""Integration tests for LiteLLM proxy routers (models, teams, keys, budgets).

Tests cross-router interactions: URL construction, header forwarding, error
propagation, and JSON body verification across the four LiteLLM proxy routers
that share the same _ensure_http / _litellm_headers pattern.
"""

import importlib.util
import os
import sys
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

_service_dir = os.path.join(os.path.dirname(__file__), "../../src/admin-api")
sys.path.insert(0, _service_dir)

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


def _fake_user():
    return UserInfo(user_id="test-admin", role="admin", is_admin=True)


app.dependency_overrides[get_current_user] = _fake_user
app.dependency_overrides[require_admin] = _fake_user


def _mock_http_response(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    resp.raise_for_status = MagicMock()
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
# 1. Models URL construction
# ============================================================================


@pytest.mark.asyncio
async def test_models_list_url_construction(client):
    """GET /models proxies to LiteLLM /model/info."""
    mock_resp = _mock_http_response(200, {"data": []})
    deps.http_client = AsyncMock()
    deps.http_client.get = AsyncMock(return_value=mock_resp)

    async with client:
        resp = await client.get("/api/v1/models")

    assert resp.status_code == 200
    url_called = deps.http_client.get.call_args[0][0]
    assert "/model/info" in url_called


# ============================================================================
# 2. Models auth header
# ============================================================================


@pytest.mark.asyncio
async def test_models_auth_header(client):
    """GET /models sends Authorization: Bearer header to LiteLLM."""
    mock_resp = _mock_http_response(200, {"data": []})
    deps.http_client = AsyncMock()
    deps.http_client.get = AsyncMock(return_value=mock_resp)

    async with client:
        await client.get("/api/v1/models")

    call_kwargs = deps.http_client.get.call_args
    headers = call_kwargs.kwargs.get("headers", {})
    assert "Authorization" in headers
    assert headers["Authorization"].startswith("Bearer ")


# ============================================================================
# 3. Teams list URL
# ============================================================================


@pytest.mark.asyncio
async def test_teams_list_url(client):
    """GET /teams proxies to LiteLLM /team/list."""
    mock_resp = _mock_http_response(200, [])
    deps.http_client = AsyncMock()
    deps.http_client.get = AsyncMock(return_value=mock_resp)

    async with client:
        resp = await client.get("/api/v1/teams")

    assert resp.status_code == 200
    url_called = deps.http_client.get.call_args[0][0]
    assert "/team/list" in url_called


# ============================================================================
# 4. Teams create URL
# ============================================================================


@pytest.mark.asyncio
async def test_teams_create_url(client):
    """POST /teams proxies to LiteLLM /team/new."""
    mock_resp = _mock_http_response(200, {"team_id": "t1"})
    deps.http_client = AsyncMock()
    deps.http_client.post = AsyncMock(return_value=mock_resp)

    async with client:
        resp = await client.post("/api/v1/teams", json={"team_alias": "eng-team"})

    assert resp.status_code == 200
    url_called = deps.http_client.post.call_args[0][0]
    assert "/team/new" in url_called


# ============================================================================
# 5. Teams get passes team_id param
# ============================================================================


@pytest.mark.asyncio
async def test_teams_get_passes_team_id(client):
    """GET /teams/{team_id} sends ?team_id= param to LiteLLM."""
    mock_resp = _mock_http_response(200, {"team_id": "team-xyz"})
    deps.http_client = AsyncMock()
    deps.http_client.get = AsyncMock(return_value=mock_resp)

    async with client:
        resp = await client.get("/api/v1/teams/team-xyz")

    assert resp.status_code == 200
    call_kwargs = deps.http_client.get.call_args
    params = call_kwargs.kwargs.get("params", {})
    assert params.get("team_id") == "team-xyz"


# ============================================================================
# 6. Keys generate URL
# ============================================================================


@pytest.mark.asyncio
async def test_keys_generate_url(client):
    """POST /keys/generate proxies to LiteLLM /key/generate."""
    mock_resp = _mock_http_response(200, {"key": "sk-test"})
    deps.http_client = AsyncMock()
    deps.http_client.post = AsyncMock(return_value=mock_resp)

    async with client:
        resp = await client.post("/api/v1/keys/generate", json={})

    assert resp.status_code == 200
    url_called = deps.http_client.post.call_args[0][0]
    assert "/key/generate" in url_called


# ============================================================================
# 7. Keys list URL
# ============================================================================


@pytest.mark.asyncio
async def test_keys_list_url(client):
    """GET /keys proxies to LiteLLM /key/list."""
    mock_resp = _mock_http_response(200, [])
    deps.http_client = AsyncMock()
    deps.http_client.get = AsyncMock(return_value=mock_resp)

    async with client:
        resp = await client.get("/api/v1/keys")

    assert resp.status_code == 200
    url_called = deps.http_client.get.call_args[0][0]
    assert "/key/list" in url_called


# ============================================================================
# 8. Budgets list URL
# ============================================================================


@pytest.mark.asyncio
async def test_budgets_list_url(client):
    """GET /budgets proxies to LiteLLM /budget/list."""
    mock_resp = _mock_http_response(200, [])
    deps.http_client = AsyncMock()
    deps.http_client.get = AsyncMock(return_value=mock_resp)

    async with client:
        resp = await client.get("/api/v1/budgets")

    assert resp.status_code == 200
    url_called = deps.http_client.get.call_args[0][0]
    assert "/budget/list" in url_called


# ============================================================================
# 9. All proxy routers 503 when no http client
# ============================================================================


@pytest.mark.asyncio
async def test_all_proxy_routers_503_when_no_http(client):
    """All four proxy routers return 503 when deps.http_client is None."""
    deps.http_client = None

    async with client:
        # Models
        r1 = await client.get("/api/v1/models")
        assert r1.status_code == 503

        # Teams
        r2 = await client.get("/api/v1/teams")
        assert r2.status_code == 503

        # Keys
        r3 = await client.get("/api/v1/keys")
        assert r3.status_code == 503

        # Budgets
        r4 = await client.get("/api/v1/budgets")
        assert r4.status_code == 503


# ============================================================================
# 10. All proxy routers forward LiteLLM errors
# ============================================================================


@pytest.mark.asyncio
async def test_all_proxy_routers_forward_litellm_errors(client):
    """All four proxy routers forward 4xx/5xx from LiteLLM as-is."""
    mock_resp_400 = _mock_http_response(400, text="Bad Request from LiteLLM")
    deps.http_client = AsyncMock()
    deps.http_client.get = AsyncMock(return_value=mock_resp_400)
    deps.http_client.post = AsyncMock(return_value=mock_resp_400)

    async with client:
        r_models = await client.get("/api/v1/models")
        assert r_models.status_code == 400

        r_teams = await client.get("/api/v1/teams")
        assert r_teams.status_code == 400

        r_keys = await client.get("/api/v1/keys")
        assert r_keys.status_code == 400

        r_budgets = await client.get("/api/v1/budgets")
        assert r_budgets.status_code == 400


# ============================================================================
# 11. Models get filters response
# ============================================================================


@pytest.mark.asyncio
async def test_models_get_filters_response(client):
    """GET /models/{model_id} filters the full model list to find a match."""
    mock_resp = _mock_http_response(
        200,
        {
            "data": [
                {"model_name": "gpt-4o", "model_info": {"id": "m1"}},
                {"model_name": "claude-3", "model_info": {"id": "m2"}},
                {"model_name": "gemini-pro", "model_info": {"id": "m3"}},
            ]
        },
    )
    deps.http_client = AsyncMock()
    deps.http_client.get = AsyncMock(return_value=mock_resp)

    async with client:
        resp = await client.get("/api/v1/models/m2")

    assert resp.status_code == 200
    assert resp.json()["model_name"] == "claude-3"


# ============================================================================
# 12. Team member add JSON body
# ============================================================================


@pytest.mark.asyncio
async def test_team_member_add_json_body(client):
    """POST /teams/{team_id}/members sends team_id and member in JSON body."""
    mock_resp = _mock_http_response(200, {"status": "ok"})
    deps.http_client = AsyncMock()
    deps.http_client.post = AsyncMock(return_value=mock_resp)

    member_data = {"role": "user", "user_id": "user-99"}

    async with client:
        resp = await client.post(
            "/api/v1/teams/team-abc/members",
            json={"member": member_data},
        )

    assert resp.status_code == 200
    call_kwargs = deps.http_client.post.call_args
    json_body = call_kwargs.kwargs.get("json", {})
    assert json_body["team_id"] == "team-abc"
    assert json_body["member"] == member_data


# ============================================================================
# 13. Team member delete JSON body
# ============================================================================


@pytest.mark.asyncio
async def test_team_member_delete_json_body(client):
    """POST /teams/{team_id}/members/delete sends team_id and user_id."""
    mock_resp = _mock_http_response(200, {"status": "ok"})
    deps.http_client = AsyncMock()
    deps.http_client.post = AsyncMock(return_value=mock_resp)

    async with client:
        resp = await client.post(
            "/api/v1/teams/team-abc/members/delete",
            json={"user_id": "user-99"},
        )

    assert resp.status_code == 200
    call_kwargs = deps.http_client.post.call_args
    json_body = call_kwargs.kwargs.get("json", {})
    assert json_body["team_id"] == "team-abc"
    assert json_body["user_id"] == "user-99"


# ============================================================================
# 14. Key update forwards body
# ============================================================================


@pytest.mark.asyncio
async def test_key_update_forwards_body(client):
    """POST /keys/update forwards the full body to LiteLLM /key/update."""
    mock_resp = _mock_http_response(200, {"status": "ok"})
    deps.http_client = AsyncMock()
    deps.http_client.post = AsyncMock(return_value=mock_resp)

    payload = {"key": "sk-existing", "max_budget": 100.0, "models": ["gpt-4o"]}

    async with client:
        resp = await client.post("/api/v1/keys/update", json=payload)

    assert resp.status_code == 200
    call_kwargs = deps.http_client.post.call_args
    url_called = call_kwargs[0][0]
    json_body = call_kwargs.kwargs.get("json", {})
    assert "/key/update" in url_called
    assert json_body["key"] == "sk-existing"
    assert json_body["max_budget"] == 100.0
    assert json_body["models"] == ["gpt-4o"]


# ============================================================================
# 15. Budget update forwards body
# ============================================================================


@pytest.mark.asyncio
async def test_budget_update_forwards_body(client):
    """POST /budgets/update forwards the full body to LiteLLM /budget/update."""
    mock_resp = _mock_http_response(200, {"status": "ok"})
    deps.http_client = AsyncMock()
    deps.http_client.post = AsyncMock(return_value=mock_resp)

    payload = {"budget_id": "b-123", "max_budget": 500.0, "rpm_limit": 100}

    async with client:
        resp = await client.post("/api/v1/budgets/update", json=payload)

    assert resp.status_code == 200
    call_kwargs = deps.http_client.post.call_args
    url_called = call_kwargs[0][0]
    json_body = call_kwargs.kwargs.get("json", {})
    assert "/budget/update" in url_called
    assert json_body["budget_id"] == "b-123"
    assert json_body["max_budget"] == 500.0
    assert json_body["rpm_limit"] == 100


# ============================================================================
# 16. Models create URL goes to /model/new
# ============================================================================


@pytest.mark.asyncio
async def test_models_create_url(client):
    """POST /models proxies to LiteLLM /model/new."""
    mock_resp = _mock_http_response(200, {"status": "ok"})
    deps.http_client = AsyncMock()
    deps.http_client.post = AsyncMock(return_value=mock_resp)

    async with client:
        resp = await client.post(
            "/api/v1/models",
            json={
                "model_name": "test-model",
                "litellm_params": {"model": "gpt-4o"},
            },
        )

    assert resp.status_code == 200
    url_called = deps.http_client.post.call_args[0][0]
    assert "/model/new" in url_called


# ============================================================================
# 17. Keys generate includes auth header
# ============================================================================


@pytest.mark.asyncio
async def test_keys_generate_auth_header(client):
    """POST /keys/generate sends Authorization: Bearer header."""
    mock_resp = _mock_http_response(200, {"key": "sk-new"})
    deps.http_client = AsyncMock()
    deps.http_client.post = AsyncMock(return_value=mock_resp)

    async with client:
        await client.post("/api/v1/keys/generate", json={})

    call_kwargs = deps.http_client.post.call_args
    headers = call_kwargs.kwargs.get("headers", {})
    assert "Authorization" in headers
    assert headers["Authorization"].startswith("Bearer ")


# ============================================================================
# 18. Budget create URL goes to /budget/new
# ============================================================================


@pytest.mark.asyncio
async def test_budgets_create_url(client):
    """POST /budgets proxies to LiteLLM /budget/new."""
    mock_resp = _mock_http_response(200, {"budget_id": "b1"})
    deps.http_client = AsyncMock()
    deps.http_client.post = AsyncMock(return_value=mock_resp)

    async with client:
        resp = await client.post("/api/v1/budgets", json={"max_budget": 100.0})

    assert resp.status_code == 200
    url_called = deps.http_client.post.call_args[0][0]
    assert "/budget/new" in url_called


# ============================================================================
# 19. Teams update URL goes to /team/update
# ============================================================================


@pytest.mark.asyncio
async def test_teams_update_url(client):
    """POST /teams/update proxies to LiteLLM /team/update."""
    mock_resp = _mock_http_response(200, {"status": "ok"})
    deps.http_client = AsyncMock()
    deps.http_client.post = AsyncMock(return_value=mock_resp)

    async with client:
        resp = await client.post(
            "/api/v1/teams/update",
            json={
                "team_id": "team-1",
                "team_alias": "new-name",
            },
        )

    assert resp.status_code == 200
    url_called = deps.http_client.post.call_args[0][0]
    assert "/team/update" in url_called


# ============================================================================
# 20. Cross-router: create model then list includes it
# ============================================================================


@pytest.mark.asyncio
async def test_cross_router_models_and_keys_both_use_same_auth(client):
    """Models and keys routers both use the same master key for auth headers."""
    mock_resp = _mock_http_response(200, {})
    deps.http_client = AsyncMock()
    deps.http_client.get = AsyncMock(return_value=mock_resp)
    deps.http_client.post = AsyncMock(return_value=mock_resp)

    async with client:
        await client.get("/api/v1/models")
        model_headers = deps.http_client.get.call_args.kwargs.get("headers", {})

        await client.post("/api/v1/keys/generate", json={})
        key_headers = deps.http_client.post.call_args.kwargs.get("headers", {})

    # Both routers should send the same Authorization header
    assert model_headers["Authorization"] == key_headers["Authorization"]
    assert "Bearer " in model_headers["Authorization"]
