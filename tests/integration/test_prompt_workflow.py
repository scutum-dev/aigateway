"""Integration tests for prompt template lifecycle with approval workflow.

Tests multi-step prompt template workflows: create -> version -> render ->
submit for review -> approve/reject, with mocked DB connections.
"""

import importlib.util
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock

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
    conn.execute.return_value = execute_return or "UPDATE 1"
    conn.fetchval.return_value = fetchval_return
    return conn


def _make_pool(conn):
    pool = MagicMock()
    ctx = AsyncMock()
    ctx.__aenter__.return_value = conn
    ctx.__aexit__.return_value = None
    pool.acquire.return_value = ctx
    return pool


def _template_row(overrides=None):
    """Return a base prompt template row dict."""
    base = {
        "id": "pt-001",
        "name": "Summarization Prompt",
        "slug": "summarize",
        "description": "Summarize text content",
        "category": "generation",
        "template_text": "Summarize the following: {{text}}",
        "variables": json.dumps([{"name": "text", "type": "string", "required": True, "default": None}]),
        "version": 1,
        "is_current": True,
        "status": "draft",
        "team_id": None,
        "model_hint": "gpt-4o",
        "tags": ["summarization", "text"],
        "created_by": "test-admin",
        "approved_by": None,
        "approved_at": None,
        "is_active": True,
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
    }
    if overrides:
        base.update(overrides)
    return base


def _approval_row(overrides=None):
    """Return a base approval row dict."""
    base = {
        "id": "appr-001",
        "template_id": "pt-001",
        "template_version": 1,
        "requested_by": "test-admin",
        "reviewer": None,
        "status": "pending",
        "comment": None,
        "requested_at": "2026-01-10T00:00:00",
        "reviewed_at": None,
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
# 1. Create template
# ============================================================================


@pytest.mark.asyncio
async def test_create_template(client):
    """POST /prompts creates a new prompt template."""
    row = _make_row(_template_row())
    conn = _make_async_conn(fetchrow_return=row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post("/api/v1/prompts", json={
            "name": "Summarization Prompt",
            "slug": "summarize",
            "template_text": "Summarize the following: {{text}}",
            "category": "generation",
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Summarization Prompt"
    assert data["slug"] == "summarize"
    assert data["status"] == "draft"
    assert data["version"] == 1


# ============================================================================
# 2. Get template by slug
# ============================================================================


@pytest.mark.asyncio
async def test_get_template_by_slug(client):
    """GET /prompts/{slug} returns the current version of a template."""
    row = _make_row(_template_row())
    conn = _make_async_conn(fetchrow_return=row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/prompts/summarize")

    assert resp.status_code == 200
    data = resp.json()
    assert data["slug"] == "summarize"
    assert data["is_current"] is True


# ============================================================================
# 3. List templates with category filter
# ============================================================================


@pytest.mark.asyncio
async def test_list_templates_with_category_filter(client):
    """GET /prompts?category=generation returns filtered templates."""
    row1 = _make_row(_template_row({"id": "pt-1", "name": "Prompt A"}))
    row2 = _make_row(_template_row({"id": "pt-2", "name": "Prompt B"}))
    conn = _make_async_conn(fetch_return=[row1, row2])
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/prompts", params={"category": "generation"})

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


# ============================================================================
# 4. Create new version
# ============================================================================


@pytest.mark.asyncio
async def test_create_new_version(client):
    """POST /prompts/{slug}/versions creates version 2."""
    current_row = _make_row(_template_row({"version": 1}))
    new_row = _make_row(_template_row({"id": "pt-002", "version": 2, "template_text": "New: {{text}}"}))

    conn = _make_async_conn()
    conn.fetchrow = AsyncMock(side_effect=[current_row, new_row])
    conn.execute = AsyncMock()
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post("/api/v1/prompts/summarize/versions", json={
            "template_text": "New: {{text}}",
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == 2


# ============================================================================
# 5. Render template with variable substitution
# ============================================================================


@pytest.mark.asyncio
async def test_render_template(client):
    """POST /prompts/{slug}/render substitutes {{variable}} placeholders."""
    row = _make_row(_template_row({"template_text": "Summarize: {{text}}"}))
    conn = _make_async_conn(fetchrow_return=row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post("/api/v1/prompts/summarize/render", json={
            "variables": {"text": "Hello world"},
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["rendered"] == "Summarize: Hello world"
    assert data["unresolved_variables"] == []


# ============================================================================
# 6. Render with unresolved variables
# ============================================================================


@pytest.mark.asyncio
async def test_render_with_unresolved_variables(client):
    """POST /prompts/{slug}/render returns unresolved variable list."""
    row = _make_row(_template_row({"template_text": "Hello {{name}}, your order {{order_id}} is ready."}))
    conn = _make_async_conn(fetchrow_return=row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post("/api/v1/prompts/summarize/render", json={
            "variables": {"name": "Alice"},
        })

    assert resp.status_code == 200
    data = resp.json()
    assert "Alice" in data["rendered"]
    assert "order_id" in data["unresolved_variables"]


# ============================================================================
# 7. Submit for review
# ============================================================================


@pytest.mark.asyncio
async def test_submit_for_review(client):
    """POST /prompts/{id}/submit-review changes status to pending_review."""
    template_row = _make_row(_template_row({"status": "draft"}))
    approval_row_data = _make_row(_approval_row({"status": "pending"}))

    conn = _make_async_conn()
    conn.fetchrow = AsyncMock(side_effect=[template_row, approval_row_data])
    conn.execute = AsyncMock()
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post("/api/v1/prompts/pt-001/submit-review")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert data["template_id"] == "pt-001"


# ============================================================================
# 8. Approve prompt
# ============================================================================


@pytest.mark.asyncio
async def test_approve_prompt(client):
    """POST /prompt-approvals/{id}/approve changes status to approved."""
    approval_row_data = _make_row(_approval_row({"status": "pending", "template_id": "pt-001"}))

    conn = _make_async_conn()
    conn.fetchrow = AsyncMock(return_value=approval_row_data)
    conn.execute = AsyncMock()
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post("/api/v1/prompt-approvals/appr-001/approve", json={
            "comment": "Looks good!",
        })

    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    # Verify execute was called to update both approval and template
    assert conn.execute.call_count >= 2


# ============================================================================
# 9. Reject prompt
# ============================================================================


@pytest.mark.asyncio
async def test_reject_prompt(client):
    """POST /prompt-approvals/{id}/reject sets status back to draft."""
    approval_row_data = _make_row(_approval_row({"status": "pending", "template_id": "pt-001"}))

    conn = _make_async_conn()
    conn.fetchrow = AsyncMock(return_value=approval_row_data)
    conn.execute = AsyncMock()
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post("/api/v1/prompt-approvals/appr-001/reject", json={
            "comment": "Needs revision",
        })

    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
    # Verify template status was also updated
    assert conn.execute.call_count >= 2


# ============================================================================
# 10. Delete prompt (soft delete)
# ============================================================================


@pytest.mark.asyncio
async def test_delete_prompt_soft_delete(client):
    """DELETE /prompts/{id} sets is_active=false."""
    conn = _make_async_conn(execute_return="UPDATE 1")
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.delete("/api/v1/prompts/pt-001")

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    # Verify the execute SQL contains is_active = false
    call_args = conn.execute.call_args[0]
    assert "is_active" in call_args[0].lower() or "is_active" in str(call_args[0])


# ============================================================================
# 11. List approvals pending
# ============================================================================


@pytest.mark.asyncio
async def test_list_approvals_pending(client):
    """GET /prompt-approvals?status=pending returns pending approvals."""
    appr1 = _make_row(_approval_row({"id": "appr-1"}))
    appr2 = _make_row(_approval_row({"id": "appr-2"}))
    conn = _make_async_conn(fetch_return=[appr1, appr2])
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/prompt-approvals", params={"status": "pending"})

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["status"] == "pending"


# ============================================================================
# 12. Update template
# ============================================================================


@pytest.mark.asyncio
async def test_update_template(client):
    """PUT /prompts/{id} updates template fields."""
    updated_row = _make_row(_template_row({"name": "Updated Prompt", "description": "Updated description"}))
    conn = _make_async_conn(fetchrow_return=updated_row)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.put("/api/v1/prompts/pt-001", json={
            "name": "Updated Prompt",
            "description": "Updated description",
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated Prompt"


# ============================================================================
# 13. Analytics returns usage stats
# ============================================================================


@pytest.mark.asyncio
async def test_analytics_returns_usage_stats(client):
    """GET /prompts/{slug}/analytics returns usage statistics."""
    template_rows = [
        _make_row({"id": "pt-001", "version": 1}),
        _make_row({"id": "pt-002", "version": 2}),
    ]
    usage_row = _make_row({
        "version": 1,
        "total_uses": 42,
        "avg_latency_ms": 150.5,
        "total_cost": 1.25,
        "total_input_tokens": 10000,
        "total_output_tokens": 5000,
    })

    conn = _make_async_conn()
    conn.fetch = AsyncMock(side_effect=[template_rows, [usage_row]])
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/prompts/summarize/analytics")

    assert resp.status_code == 200
    data = resp.json()
    assert data["slug"] == "summarize"
    assert data["versions"] == [1, 2]
    assert len(data["usage"]) == 1
    assert data["usage"][0]["total_uses"] == 42


# ============================================================================
# 14. Get template not found
# ============================================================================


@pytest.mark.asyncio
async def test_get_template_not_found(client):
    """GET /prompts/{slug} returns 404 for non-existent slug."""
    conn = _make_async_conn(fetchrow_return=None)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.get("/api/v1/prompts/nonexistent")

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ============================================================================
# 15. Approve not found
# ============================================================================


@pytest.mark.asyncio
async def test_approve_not_found(client):
    """POST /prompt-approvals/{id}/approve returns 404 for missing approval."""
    conn = _make_async_conn(fetchrow_return=None)
    deps.db_pool = _make_pool(conn)

    async with client:
        resp = await client.post("/api/v1/prompt-approvals/nonexistent/approve", json={})

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
