"""End-to-end error resilience tests for the Admin API.

These tests run against the ASGI app with mocked DB/HTTP (same pattern as
the unit tests) and exercise error handling: database unavailable, LiteLLM
unreachable, validation failures, and concurrent state scenarios.
"""

import importlib.util
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
    """Create a MagicMock that behaves like an asyncpg Record."""
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
# Database Unavailable
# ============================================================================


class TestDatabaseUnavailable:
    """All major endpoint types return 503 when deps.db_pool is None."""

    @pytest.mark.asyncio
    async def test_get_list_organizations_db_unavailable(self, client):
        """GET /organizations returns 503 when db_pool is None."""
        deps.db_pool = None

        async with client:
            resp = await client.get("/api/v1/organizations")

        assert resp.status_code == 503
        assert "Database not available" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_post_create_organization_db_unavailable(self, client):
        """POST /organizations returns 503 when db_pool is None."""
        deps.db_pool = None

        async with client:
            resp = await client.post(
                "/api/v1/organizations",
                json={"name": "Test", "slug": "test"},
            )

        assert resp.status_code == 503
        assert "Database not available" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_put_update_organization_db_unavailable(self, client):
        """PUT /organizations/{id} returns 503 when db_pool is None."""
        deps.db_pool = None

        async with client:
            resp = await client.put(
                "/api/v1/organizations/org-001",
                json={"name": "Updated"},
            )

        assert resp.status_code == 503
        assert "Database not available" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_delete_organization_db_unavailable(self, client):
        """DELETE /organizations/{id} returns 503 when db_pool is None."""
        deps.db_pool = None

        async with client:
            resp = await client.delete("/api/v1/organizations/org-001")

        assert resp.status_code == 503
        assert "Database not available" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_ab_tests_db_unavailable(self, client):
        """GET /ab-tests returns 503 when db_pool is None."""
        deps.db_pool = None

        async with client:
            resp = await client.get("/api/v1/ab-tests")

        assert resp.status_code == 503
        assert "Database not available" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_post_rate_limits_db_unavailable(self, client):
        """POST /rate-limits returns 503 when db_pool is None."""
        deps.db_pool = None

        async with client:
            resp = await client.post(
                "/api/v1/rate-limits",
                json={"name": "Test", "scope": "global", "rpm_limit": 100},
            )

        assert resp.status_code == 503
        assert "Database not available" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_prompts_db_unavailable(self, client):
        """GET /prompts returns 503 when db_pool is None."""
        deps.db_pool = None

        async with client:
            resp = await client.get("/api/v1/prompts")

        assert resp.status_code == 503
        assert "Database not available" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_audit_logs_db_unavailable(self, client):
        """GET /audit-logs returns 503 when db_pool is None."""
        deps.db_pool = None

        async with client:
            resp = await client.get("/api/v1/audit-logs")

        assert resp.status_code == 503
        assert "Database not available" in resp.json()["detail"]


# ============================================================================
# LiteLLM Unreachable
# ============================================================================


class TestLiteLLMUnreachable:
    """Endpoints that proxy to LiteLLM return 503 or propagate errors."""

    @pytest.mark.asyncio
    async def test_models_list_no_http_client(self, client):
        """GET /models returns 503 when http_client is None."""
        deps.http_client = None

        async with client:
            resp = await client.get("/api/v1/models")

        assert resp.status_code == 503
        assert "HTTP client not available" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_models_get_no_http_client(self, client):
        """GET /models/{id} returns 503 when http_client is None."""
        deps.http_client = None

        async with client:
            resp = await client.get("/api/v1/models/some-model")

        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_models_create_no_http_client(self, client):
        """POST /models returns 503 when http_client is None."""
        deps.http_client = None

        async with client:
            resp = await client.post(
                "/api/v1/models",
                json={
                    "model_name": "test-model",
                    "litellm_params": {"model": "gpt-4o"},
                },
            )

        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_models_litellm_returns_500(self, client):
        """GET /models with LiteLLM returning 500 -> propagates error."""
        mock_resp = _mock_http_response(500, text="Internal Server Error")
        deps.http_client = AsyncMock()
        deps.http_client.get = AsyncMock(return_value=mock_resp)

        async with client:
            resp = await client.get("/api/v1/models")

        assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_sync_alias_no_http_client(self, client):
        """Sync alias with no http_client -> 503."""
        pool, conn = _setup_db_pool()
        deps.http_client = None

        dep_row = _make_mock_row({
            "id": "dep-001",
            "model_name": "old-model",
            "replacement_model": "new-model",
            "deprecation_date": None,
            "sunset_date": None,
            "message": None,
            "created_at": "2026-01-01T00:00:00",
        })
        conn.fetchrow.return_value = dep_row

        async with client:
            resp = await client.post("/api/v1/model-deprecations/dep-001/sync-alias")

        assert resp.status_code == 503
        assert "HTTP client not available" in resp.json()["detail"]


# ============================================================================
# Validation Errors
# ============================================================================


class TestValidationErrors:
    """Request validation failures return proper 422 and 404 responses."""

    @pytest.mark.asyncio
    async def test_create_org_empty_body_returns_422(self, client):
        """POST /organizations with empty body -> 422."""
        pool, conn = _setup_db_pool()

        async with client:
            resp = await client.post(
                "/api/v1/organizations",
                json={},
            )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_org_missing_required_fields_returns_422(self, client):
        """POST /organizations missing required slug -> 422."""
        pool, conn = _setup_db_pool()

        async with client:
            resp = await client.post(
                "/api/v1/organizations",
                json={"name": "Has Name Only"},
            )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_ab_test_invalid_types_returns_422(self, client):
        """POST /ab-tests with invalid field types -> 422."""
        pool, conn = _setup_db_pool()

        async with client:
            resp = await client.post(
                "/api/v1/ab-tests",
                json={
                    "name": 12345,  # should be string, but Pydantic coerces ints
                    "base_model": "gpt-4o",
                    "variant_model": "claude-3-5-sonnet",
                    "traffic_split_percent": "not-an-int",
                },
            )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_update_nonexistent_org_returns_404(self, client):
        """PUT /organizations/{id} with nonexistent ID -> 404."""
        pool, conn = _setup_db_pool()
        conn.fetchrow.return_value = None

        async with client:
            resp = await client.put(
                "/api/v1/organizations/nonexistent-id",
                json={"name": "Updated Name"},
            )

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_nonexistent_ab_test_returns_404(self, client):
        """GET /ab-tests/{id} with nonexistent ID -> 404."""
        pool, conn = _setup_db_pool()
        conn.fetchrow.return_value = None

        async with client:
            resp = await client.get("/api/v1/ab-tests/nonexistent-uuid")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_org_returns_404(self, client):
        """DELETE /organizations/{id} with nonexistent ID -> 404."""
        pool, conn = _setup_db_pool()
        conn.execute.return_value = "DELETE 0"

        with patch("routers.organizations.log_audit_event", new_callable=AsyncMock):
            async with client:
                resp = await client.delete("/api/v1/organizations/nonexistent-id")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_update_org_no_fields_returns_400(self, client):
        """PUT /organizations/{id} with empty update body -> 400."""
        pool, conn = _setup_db_pool()

        async with client:
            resp = await client.put(
                "/api/v1/organizations/org-001",
                json={},
            )

        assert resp.status_code == 400
        assert "No fields to update" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_rate_limit_no_fields_returns_400(self, client):
        """PUT /rate-limits/{id} with empty update body -> 400."""
        pool, conn = _setup_db_pool()

        async with client:
            resp = await client.put(
                "/api/v1/rate-limits/rl-001",
                json={},
            )

        assert resp.status_code == 400
        assert "No fields to update" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_delete_nonexistent_subscription_returns_404(self, client):
        """DELETE /events/subscriptions/{id} with nonexistent ID -> 404."""
        pool, conn = _setup_db_pool()
        conn.execute.return_value = "DELETE 0"

        async with client:
            resp = await client.delete("/api/v1/events/subscriptions/nonexistent-sub")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_nonexistent_rate_limit_returns_404(self, client):
        """GET /rate-limits/{id} with nonexistent ID -> 404."""
        pool, conn = _setup_db_pool()
        conn.fetchrow.return_value = None

        async with client:
            resp = await client.get("/api/v1/rate-limits/nonexistent-uuid")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_event_subscription_missing_fields_422(self, client):
        """POST /events/subscriptions with missing required fields -> 422."""
        pool, conn = _setup_db_pool()

        async with client:
            resp = await client.post(
                "/api/v1/events/subscriptions",
                json={"name": "Partial"},
            )

        assert resp.status_code == 422


# ============================================================================
# Concurrent State
# ============================================================================


class TestConcurrentState:
    """Verify mock DB calls are sequenced and state resets properly."""

    @pytest.mark.asyncio
    async def test_sequential_org_create_and_read(self, client):
        """Two sequential requests: create org then list orgs - DB calls are sequenced."""
        pool, conn = _setup_db_pool()

        org_row = _make_mock_row({
            "id": "org-seq-001",
            "name": "Sequential Org",
            "slug": "sequential-org",
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
        conn.fetch.return_value = [org_row]
        conn.execute.return_value = "INSERT 1"

        with patch("routers.organizations.log_audit_event", new_callable=AsyncMock):
            async with client:
                # Request 1: create
                resp1 = await client.post(
                    "/api/v1/organizations",
                    json={"name": "Sequential Org", "slug": "sequential-org"},
                )
                assert resp1.status_code == 200

                # Request 2: list
                resp2 = await client.get("/api/v1/organizations")
                assert resp2.status_code == 200

        # Verify fetchrow was called at least once (for create)
        assert conn.fetchrow.call_count >= 1
        # Verify fetch was called at least once (for list)
        assert conn.fetch.call_count >= 1

    @pytest.mark.asyncio
    async def test_sequential_ab_test_operations(self, client):
        """Two sequential A/B test reads use separate mock returns."""
        pool, conn = _setup_db_pool()

        test1_row = _make_mock_row({
            "id": "ab-seq-001",
            "name": "Test A",
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

        test2_row = _make_mock_row({
            "id": "ab-seq-002",
            "name": "Test B",
            "status": "running",
            "base_model": "gpt-4o",
            "variant_model": "claude-3-5-sonnet",
            "traffic_split_percent": 20,
            "success_metric": "avg_latency_ms",
            "promotion_threshold": None,
            "rollback_threshold": None,
            "auto_promote": False,
            "auto_rollback": True,
            "started_at": "2026-01-01T01:00:00",
            "completed_at": None,
            "created_by": "test-admin",
            "created_at": "2026-01-01T00:00:00",
        })

        # get_ab_test calls fetchrow twice: once for the test, once for snapshot
        conn.fetchrow.side_effect = [
            test1_row, None,  # get test1: row + no snapshot
            test2_row, None,  # get test2: row + no snapshot
        ]

        async with client:
            resp1 = await client.get("/api/v1/ab-tests/ab-seq-001")
            assert resp1.status_code == 200
            assert resp1.json()["name"] == "Test A"
            assert resp1.json()["status"] == "draft"

            resp2 = await client.get("/api/v1/ab-tests/ab-seq-002")
            assert resp2.status_code == 200
            assert resp2.json()["name"] == "Test B"
            assert resp2.json()["status"] == "running"

        # Verify all four fetchrow calls were made
        assert conn.fetchrow.call_count == 4

    @pytest.mark.asyncio
    async def test_rate_limit_cache_resets_between_tests(self, client):
        """Verify _rate_limit_cache resets between tests (via _reset_deps fixture)."""
        # The autouse fixture should have set cache to bypass middleware
        assert _main_mod._rate_limit_cache["value"] == 0
        assert _main_mod._rate_limit_cache["expires_at"] == 9999999999.0
        assert len(_main_mod._inmemory_requests) == 0

        # Simulate setting cache values
        _main_mod._rate_limit_cache["value"] = 500
        _main_mod._rate_limit_cache["expires_at"] = 99999999.0
        _main_mod._inmemory_requests.extend([1.0, 2.0, 3.0])

        # Within the same test, values persist
        assert _main_mod._rate_limit_cache["value"] == 500
        assert len(_main_mod._inmemory_requests) == 3

    @pytest.mark.asyncio
    async def test_rate_limit_cache_is_clean_after_previous_test(self, client):
        """Confirm that the cache was reset by the fixture after the previous test."""
        assert _main_mod._rate_limit_cache["value"] == 0
        assert _main_mod._rate_limit_cache["expires_at"] == 9999999999.0
        assert len(_main_mod._inmemory_requests) == 0

    @pytest.mark.asyncio
    async def test_deps_reset_between_tests(self, client):
        """Verify deps are properly restored after modification."""
        _original_pool = deps.db_pool
        _original_http = deps.http_client

        # Modify deps
        deps.db_pool = "modified"
        deps.http_client = "modified"

        # The fixture will restore after this test completes
        assert deps.db_pool == "modified"
        assert deps.http_client == "modified"


# ============================================================================
# Cross-Router Error Propagation
# ============================================================================


class TestCrossRouterErrorPropagation:
    """Errors in one router call do not leak state into subsequent calls."""

    @pytest.mark.asyncio
    async def test_db_error_followed_by_success(self):
        """First request fails with 503, second succeeds after restoring db_pool."""
        transport = httpx.ASGITransport(app=app)

        # First: no DB
        deps.db_pool = None

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c1:
            resp1 = await c1.get("/api/v1/organizations")
            assert resp1.status_code == 503

        # Restore DB and try again
        pool, conn = _setup_db_pool()
        conn.fetch.return_value = []

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c2:
            resp2 = await c2.get("/api/v1/organizations")
            assert resp2.status_code == 200
            assert resp2.json() == []

    @pytest.mark.asyncio
    async def test_litellm_error_does_not_affect_db_endpoints(self, client):
        """LiteLLM error on models endpoint does not affect org endpoint."""
        pool, conn = _setup_db_pool()
        deps.http_client = AsyncMock()

        # Models endpoint: LiteLLM returns 500
        mock_resp = _mock_http_response(500, text="Internal Server Error")
        deps.http_client.get = AsyncMock(return_value=mock_resp)

        # Orgs endpoint: DB returns data
        org_row = _make_mock_row({
            "id": "org-001",
            "name": "Acme",
            "slug": "acme",
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
        conn.fetch.return_value = [org_row]

        async with client:
            # Models fails
            resp1 = await client.get("/api/v1/models")
            assert resp1.status_code == 500

            # Orgs still works
            resp2 = await client.get("/api/v1/organizations")
            assert resp2.status_code == 200
            assert len(resp2.json()) == 1

    @pytest.mark.asyncio
    async def test_health_endpoint_always_available(self, client):
        """Health endpoint works regardless of db/http state."""
        deps.db_pool = None
        deps.http_client = None

        async with client:
            resp = await client.get("/health")

        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
