"""Unit tests for the Prompts router.

Tests prompt template CRUD, versioning, approval workflow (submit, approve,
reject), render with variable substitution, and analytics.
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


# ---------------------------------------------------------------------------
# Shared mock data
# ---------------------------------------------------------------------------

_prompt_row = _make_row(
    {
        "id": "prompt-uuid-1",
        "name": "Summarizer",
        "slug": "summarizer",
        "description": "Summarize text",
        "category": "utility",
        "template_text": "Summarize: {{text}}",
        "variables": '[{"name":"text","type":"string","required":true}]',
        "version": 1,
        "is_current": True,
        "status": "approved",
        "team_id": None,
        "model_hint": "gpt-4o-mini",
        "tags": ["summarize"],
        "created_by": "admin",
        "approved_by": "admin",
        "approved_at": "2024-01-01",
        "is_active": True,
        "created_at": "2024-01-01T00:00:00",
        "updated_at": None,
    }
)

_approval_row = _make_row(
    {
        "id": "appr-uuid-1",
        "template_id": "prompt-uuid-1",
        "template_version": 1,
        "requested_by": "admin",
        "reviewer": None,
        "status": "pending",
        "comment": None,
        "requested_at": "2024-01-01T00:00:00",
        "reviewed_at": None,
    }
)


# ============================================================================
# Prompt Template CRUD
# ============================================================================


@pytest.mark.asyncio
async def test_list_prompts(client):
    """GET /prompts returns active, current prompt templates."""
    conn = _make_async_conn(fetch_return=[_prompt_row])
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/prompts")

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["name"] == "Summarizer"
    assert data[0]["slug"] == "summarizer"


@pytest.mark.asyncio
async def test_list_prompts_no_db(client):
    """GET /prompts returns 503 when database is unavailable."""
    deps.db_pool = None

    async with client:
        resp = await client.get("/api/v1/prompts")

    assert resp.status_code == 503
    assert "Database not available" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_prompt(client):
    """POST /prompts creates a new prompt template."""
    conn = _make_async_conn(fetchrow_return=_prompt_row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post(
            "/api/v1/prompts",
            json={
                "name": "Summarizer",
                "slug": "summarizer",
                "template_text": "Summarize: {{text}}",
                "variables": [{"name": "text", "type": "string", "required": True}],
                "model_hint": "gpt-4o-mini",
                "tags": ["summarize"],
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Summarizer"
    assert data["slug"] == "summarizer"
    conn.fetchrow.assert_called_once()


@pytest.mark.asyncio
async def test_get_prompt_by_slug(client):
    """GET /prompts/{slug} returns the current active version by slug."""
    conn = _make_async_conn(fetchrow_return=_prompt_row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/prompts/summarizer")

    assert resp.status_code == 200
    data = resp.json()
    assert data["slug"] == "summarizer"
    assert data["version"] == 1
    assert data["is_current"] is True


@pytest.mark.asyncio
async def test_get_prompt_not_found(client):
    """GET /prompts/{slug} returns 404 for nonexistent slug."""
    conn = _make_async_conn(fetchrow_return=None)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/prompts/nonexistent")

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_list_versions(client):
    """GET /prompts/{slug}/versions returns all versions for a slug."""
    v1 = _prompt_row
    v2 = _make_row(
        {
            **{k: _prompt_row[k] for k in _prompt_row.keys()},
            "id": "prompt-uuid-2",
            "version": 2,
            "is_current": True,
        }
    )
    conn = _make_async_conn(fetch_return=[v2, v1])
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/prompts/summarizer/versions")

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2


@pytest.mark.asyncio
async def test_update_prompt(client):
    """PUT /prompts/{id} updates a prompt template."""
    updated_row = _make_row(
        {
            **{k: _prompt_row[k] for k in _prompt_row.keys()},
            "name": "Updated Summarizer",
            "updated_at": "2024-01-02T00:00:00",
        }
    )
    conn = _make_async_conn(fetchrow_return=updated_row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.put(
            "/api/v1/prompts/prompt-uuid-1",
            json={
                "name": "Updated Summarizer",
            },
        )

    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Summarizer"


@pytest.mark.asyncio
async def test_update_prompt_not_found(client):
    """PUT /prompts/{id} returns 404 for nonexistent template."""
    conn = _make_async_conn(fetchrow_return=None)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.put(
            "/api/v1/prompts/nonexistent-uuid",
            json={
                "name": "Updated",
            },
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_prompt(client):
    """DELETE /prompts/{id} soft-deletes a prompt template."""
    conn = _make_async_conn(execute_return="UPDATE 1")
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.delete("/api/v1/prompts/prompt-uuid-1")

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_delete_prompt_not_found(client):
    """DELETE /prompts/{id} returns 404 for nonexistent template."""
    conn = _make_async_conn(execute_return="UPDATE 0")
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.delete("/api/v1/prompts/nonexistent-uuid")

    assert resp.status_code == 404


# ============================================================================
# Render
# ============================================================================


@pytest.mark.asyncio
async def test_render_prompt(client):
    """POST /prompts/{slug}/render substitutes variables and returns rendered text."""
    conn = _make_async_conn(fetchrow_return=_prompt_row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post(
            "/api/v1/prompts/summarizer/render",
            json={
                "variables": {"text": "Hello, world!"},
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["rendered"] == "Summarize: Hello, world!"
    assert data["unresolved_variables"] == []
    assert data["template_version"] == 1


@pytest.mark.asyncio
async def test_render_prompt_not_found(client):
    """POST /prompts/{slug}/render returns 404 for nonexistent slug."""
    conn = _make_async_conn(fetchrow_return=None)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post(
            "/api/v1/prompts/nonexistent/render",
            json={
                "variables": {"text": "Hello"},
            },
        )

    assert resp.status_code == 404


# ============================================================================
# Approval Workflow
# ============================================================================


@pytest.mark.asyncio
async def test_submit_review(client):
    """POST /prompts/{id}/submit-review creates an approval request."""
    conn = _make_async_conn()
    # First fetchrow: find the template; Second fetchrow: create approval record
    conn.fetchrow.side_effect = [_prompt_row, _approval_row]
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post("/api/v1/prompts/prompt-uuid-1/submit-review")

    assert resp.status_code == 200
    data = resp.json()
    assert data["template_id"] == "prompt-uuid-1"
    assert data["status"] == "pending"
    # Verify template status was updated to pending_review
    conn.execute.assert_called_once()


@pytest.mark.asyncio
async def test_list_approvals(client):
    """GET /prompt-approvals returns pending approval requests."""
    conn = _make_async_conn(fetch_return=[_approval_row])
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/prompt-approvals")

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["status"] == "pending"


@pytest.mark.asyncio
async def test_approve_prompt(client):
    """POST /prompt-approvals/{id}/approve approves a pending template."""
    conn = _make_async_conn(fetchrow_return=_approval_row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post(
            "/api/v1/prompt-approvals/appr-uuid-1/approve",
            json={
                "comment": "Looks good",
            },
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    # Should update both the approval record and the template
    assert conn.execute.call_count == 2


@pytest.mark.asyncio
async def test_approve_not_found(client):
    """POST /prompt-approvals/{id}/approve returns 404 for missing or already reviewed."""
    conn = _make_async_conn(fetchrow_return=None)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post("/api/v1/prompt-approvals/nonexistent/approve")

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reject_prompt(client):
    """POST /prompt-approvals/{id}/reject rejects a pending template."""
    conn = _make_async_conn(fetchrow_return=_approval_row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post(
            "/api/v1/prompt-approvals/appr-uuid-1/reject",
            json={
                "comment": "Needs revision",
            },
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
    # Should update both the approval record and the template back to draft
    assert conn.execute.call_count == 2


# ============================================================================
# Analytics
# ============================================================================


@pytest.mark.asyncio
async def test_prompt_analytics(client):
    """GET /prompts/{slug}/analytics returns usage stats across versions."""
    template_rows = [
        _make_row({"id": "prompt-uuid-1", "version": 1}),
        _make_row({"id": "prompt-uuid-2", "version": 2}),
    ]
    usage_rows = [
        _make_row(
            {
                "version": 1,
                "total_uses": 50,
                "avg_latency_ms": 200.5,
                "total_cost": 1.25,
                "total_input_tokens": 10000,
                "total_output_tokens": 5000,
            }
        ),
        _make_row(
            {
                "version": 2,
                "total_uses": 30,
                "avg_latency_ms": 180.0,
                "total_cost": 0.75,
                "total_input_tokens": 6000,
                "total_output_tokens": 3000,
            }
        ),
    ]
    conn = _make_async_conn()
    # First fetch: template IDs/versions; Second fetch: usage stats
    conn.fetch.side_effect = [template_rows, usage_rows]
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/prompts/summarizer/analytics")

    assert resp.status_code == 200
    data = resp.json()
    assert data["slug"] == "summarizer"
    assert data["versions"] == [1, 2]
    assert len(data["usage"]) == 2
    assert data["usage"][0]["total_uses"] == 50
    assert data["usage"][1]["total_uses"] == 30


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
