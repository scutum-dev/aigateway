"""Unit tests for src/admin-api/routers/trial_signup.py.

Covers the three routes (signup / verify / status) plus the helpers
(_verify_turnstile, _check_rate_limit). Mocks asyncpg + httpx + SMTP so
the tests are pure-Python — no Postgres / Cloudflare / mail server needed.

Pattern mirrors tests/unit/test_admin_routers.py.
"""

import importlib.util
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# ---- module loading (mirrors test_admin_routers.py) -------------------------

_service_dir = os.path.join(os.path.dirname(__file__), "../../src/admin-api")
sys.path.insert(0, _service_dir)

# Pre-mock heavy deps that main.py loads at module level — don't actually
# need them for router tests.
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

_spec = importlib.util.spec_from_file_location("admin_api_main", os.path.join(_service_dir, "main.py"))
_main_mod = importlib.util.module_from_spec(_spec)
sys.modules["admin_api_main"] = _main_mod
_spec.loader.exec_module(_main_mod)

app = _main_mod.app

import deps  # noqa: E402
from routers import trial_signup as ts  # noqa: E402

# ---- helpers ----------------------------------------------------------------


def _make_pool(conn):
    pool = MagicMock()
    ctx = AsyncMock()
    ctx.__aenter__.return_value = conn
    ctx.__aexit__.return_value = None
    pool.acquire.return_value = ctx
    # `conn.transaction()` is called synchronously and returns an async context
    # manager. AsyncMock would return a coroutine wrapping the context, which
    # breaks `async with`. So we set `transaction` itself to a regular MagicMock
    # that returns a pre-built async-ctx mock.
    tx_ctx = AsyncMock()
    tx_ctx.__aenter__.return_value = None
    tx_ctx.__aexit__.return_value = None
    conn.transaction = MagicMock(return_value=tx_ctx)
    return pool


def _trial_id():
    """A real UUID string so the verify/status routes' uuid.UUID() check passes."""
    return "11111111-1111-4111-8111-111111111111"


@pytest.fixture(autouse=True)
def _reset_deps():
    original_pool = deps.db_pool
    original_http = deps.http_client
    original_redis = deps.redis_client
    # Pin the global-rate-limit cache to a sentinel so the middleware short-circuits
    # without hitting our mocked conn (it would otherwise consume a fetchrow call).
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


# ---- POST /api/v1/trial-signup ---------------------------------------------


class TestSignupCreate:
    @pytest.mark.asyncio
    async def test_happy_path_returns_pending_verification(self, client):
        """Valid email + valid Turnstile + clean DB → 200, pending_verification."""
        conn = AsyncMock()
        # Rate-limit count + dedupe lookup + INSERTs.
        conn.fetchval.side_effect = [
            0,  # rate-limit count
            "user-uuid",  # users INSERT RETURNING id
            "org-uuid",  # organizations INSERT RETURNING id
            _trial_id(),  # trial_instances INSERT RETURNING id
        ]
        conn.fetchrow.side_effect = [None]  # no existing user
        deps.db_pool = _make_pool(conn)

        # Bypass Turnstile network call — patch the helper directly.
        with patch.object(ts, "_verify_turnstile", new=AsyncMock(return_value=True)):
            async with client:
                resp = await client.post(
                    "/api/v1/trial-signup",
                    json={"email": "evaluator@example.com", "turnstile_token": "valid-token"},
                )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "pending_verification"
        assert body["trial_id"] == _trial_id()

    @pytest.mark.asyncio
    async def test_rate_limited_returns_429(self, client):
        """Per-IP rate limit blocks a 6th attempt in the window."""
        conn = AsyncMock()
        conn.fetchval.return_value = ts.SIGNUP_RATE_LIMIT_MAX  # already at the cap
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.post(
                "/api/v1/trial-signup",
                json={"email": "spam@example.com", "turnstile_token": "x"},
            )
        assert resp.status_code == 429

    @pytest.mark.asyncio
    async def test_failed_turnstile_returns_400(self, client):
        """Turnstile says no → 400, no DB writes other than the attempt log."""
        conn = AsyncMock()
        conn.fetchval.return_value = 0
        deps.db_pool = _make_pool(conn)

        with patch.object(ts, "_verify_turnstile", new=AsyncMock(return_value=False)):
            async with client:
                resp = await client.post(
                    "/api/v1/trial-signup",
                    json={"email": "bot@example.com", "turnstile_token": "fake"},
                )
        assert resp.status_code == 400
        assert "bot-check" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_duplicate_email_returns_409(self, client):
        """An existing trial for this email → 409 with a helpful message."""
        conn = AsyncMock()
        conn.fetchval.return_value = 0
        # First fetchrow: existing user lookup. Second: existing trial lookup.
        conn.fetchrow.side_effect = [
            {"id": "existing-user-uuid"},
            {"id": "existing-trial-uuid", "status": "active"},
        ]
        deps.db_pool = _make_pool(conn)

        with patch.object(ts, "_verify_turnstile", new=AsyncMock(return_value=True)):
            async with client:
                resp = await client.post(
                    "/api/v1/trial-signup",
                    json={"email": "returning@example.com", "turnstile_token": "valid"},
                )
        assert resp.status_code == 409
        assert "trial already exists" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_invalid_email_returns_422(self, client):
        """Pydantic EmailStr rejects malformed addresses with 422."""
        async with client:
            resp = await client.post(
                "/api/v1/trial-signup",
                json={"email": "not-an-email", "turnstile_token": "x"},
            )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_db_unavailable_returns_503(self, client):
        deps.db_pool = None
        async with client:
            resp = await client.post(
                "/api/v1/trial-signup",
                json={"email": "user@example.com", "turnstile_token": "x"},
            )
        assert resp.status_code == 503


# ---- GET /api/v1/trial-signup/{id}/verify ----------------------------------


class TestSignupVerify:
    """Verify endpoint is the email-click target. After this PR it 303-redirects
    to /try?... so users land on a viewable page; the asserts check redirect
    targets rather than JSON bodies."""

    @pytest.mark.asyncio
    async def test_valid_token_flips_to_provisioning(self, client):
        token = "valid-verification-token"
        conn = AsyncMock()
        conn.fetchrow.return_value = {
            "id": _trial_id(),
            "status": "pending_verification",
            "verification_token": token,
            "verification_expires_at": datetime.now(timezone.utc) + timedelta(hours=12),
            "user_id": "user-uuid",
            "org_id": "org-uuid",
        }
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get(f"/api/v1/trial-signup/{_trial_id()}/verify?token={token}", follow_redirects=False)

        assert resp.status_code == 303
        assert f"trial_id={_trial_id()}" in resp.headers["location"]
        # The route must NOTIFY so the provisioner picks the row up.
        notify_calls = [c for c in conn.execute.call_args_list if "pg_notify" in str(c)]
        assert len(notify_calls) == 1, "expected exactly one pg_notify call after verification"

    @pytest.mark.asyncio
    async def test_bad_token_redirects_with_invalid_error(self, client):
        conn = AsyncMock()
        conn.fetchrow.return_value = {
            "id": _trial_id(),
            "status": "pending_verification",
            "verification_token": "the-real-token",
            "verification_expires_at": datetime.now(timezone.utc) + timedelta(hours=12),
            "user_id": "user-uuid",
            "org_id": "org-uuid",
        }
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get(
                f"/api/v1/trial-signup/{_trial_id()}/verify?token=wrong-token", follow_redirects=False
            )
        assert resp.status_code == 303
        assert "error=invalid_token" in resp.headers["location"]

    @pytest.mark.asyncio
    async def test_expired_token_redirects_with_expired_error(self, client):
        token = "expired-token"
        conn = AsyncMock()
        conn.fetchrow.return_value = {
            "id": _trial_id(),
            "status": "pending_verification",
            "verification_token": token,
            # An hour in the past — the link has gone stale.
            "verification_expires_at": datetime.now(timezone.utc) - timedelta(hours=1),
            "user_id": "user-uuid",
            "org_id": "org-uuid",
        }
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get(f"/api/v1/trial-signup/{_trial_id()}/verify?token={token}", follow_redirects=False)
        assert resp.status_code == 303
        assert "error=expired" in resp.headers["location"]

    @pytest.mark.asyncio
    async def test_already_verified_is_idempotent(self, client):
        """Clicking the link twice doesn't crash — second click redirects without re-firing NOTIFY."""
        conn = AsyncMock()
        conn.fetchrow.return_value = {
            "id": _trial_id(),
            "status": "active",
            "verification_token": None,
            "verification_expires_at": None,
            "user_id": "user-uuid",
            "org_id": "org-uuid",
        }
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get(f"/api/v1/trial-signup/{_trial_id()}/verify?token=anything", follow_redirects=False)
        assert resp.status_code == 303
        assert f"trial_id={_trial_id()}" in resp.headers["location"]
        # Idempotent: no NOTIFY on a re-click.
        notify_calls = [c for c in conn.execute.call_args_list if "pg_notify" in str(c)]
        assert len(notify_calls) == 0

    @pytest.mark.asyncio
    async def test_unknown_trial_redirects_with_not_found(self, client):
        conn = AsyncMock()
        conn.fetchrow.return_value = None
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get(f"/api/v1/trial-signup/{_trial_id()}/verify?token=x", follow_redirects=False)
        assert resp.status_code == 303
        assert "error=not_found" in resp.headers["location"]

    @pytest.mark.asyncio
    async def test_invalid_uuid_redirects_with_invalid(self, client):
        deps.db_pool = _make_pool(AsyncMock())
        async with client:
            resp = await client.get("/api/v1/trial-signup/not-a-uuid/verify?token=x", follow_redirects=False)
        assert resp.status_code == 303
        assert "error=invalid" in resp.headers["location"]


# ---- GET /api/v1/trial-signup/{id}/status ----------------------------------


class TestSignupStatus:
    @pytest.mark.asyncio
    async def test_active_returns_url(self, client):
        conn = AsyncMock()
        conn.fetchrow.return_value = {
            "status": "active",
            "fqdn": "trial-abc123.trial.scutum.dev",
            "provision_error": None,
            "expires_at": datetime(2026, 6, 1, tzinfo=timezone.utc),
        }
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get(f"/api/v1/trial-signup/{_trial_id()}/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "active"
        assert body["url"] == "https://trial-abc123.trial.scutum.dev"
        assert body["error"] is None

    @pytest.mark.asyncio
    async def test_failed_surfaces_error(self, client):
        conn = AsyncMock()
        conn.fetchrow.return_value = {
            "status": "failed",
            "fqdn": None,
            "provision_error": "Fly API returned 500: capacity",
            "expires_at": None,
        }
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get(f"/api/v1/trial-signup/{_trial_id()}/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "failed"
        assert body["error"] == "Fly API returned 500: capacity"
        assert body["url"] is None

    @pytest.mark.asyncio
    async def test_provisioning_returns_no_url_yet(self, client):
        conn = AsyncMock()
        conn.fetchrow.return_value = {
            "status": "provisioning",
            "fqdn": None,
            "provision_error": None,
            "expires_at": None,
        }
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get(f"/api/v1/trial-signup/{_trial_id()}/status")
        body = resp.json()
        assert body["status"] == "provisioning"
        assert body["url"] is None

    @pytest.mark.asyncio
    async def test_unknown_returns_404(self, client):
        conn = AsyncMock()
        conn.fetchrow.return_value = None
        deps.db_pool = _make_pool(conn)

        async with client:
            resp = await client.get(f"/api/v1/trial-signup/{_trial_id()}/status")
        assert resp.status_code == 404


# ---- _verify_turnstile helper ----------------------------------------------


class TestVerifyTurnstileHelper:
    @pytest.mark.asyncio
    async def test_dev_mode_accepts_any_non_empty_token(self):
        """When TURNSTILE_SECRET_KEY is unset, any non-empty token passes."""
        with patch.object(ts, "TURNSTILE_SECRET_KEY", ""):
            assert await ts._verify_turnstile("anything", source_ip="1.2.3.4") is True
            assert await ts._verify_turnstile("", source_ip=None) is False

    @pytest.mark.asyncio
    async def test_real_mode_calls_cloudflare_endpoint(self):
        """With a secret set, we POST to Cloudflare and honour the success flag."""
        client = AsyncMock()
        success_resp = MagicMock()
        success_resp.json.return_value = {"success": True}
        client.post.return_value = success_resp
        deps.http_client = client

        with patch.object(ts, "TURNSTILE_SECRET_KEY", "secret-xyz"):
            assert await ts._verify_turnstile("good-token", source_ip="1.2.3.4") is True
            client.post.assert_called_once()
            args, kwargs = client.post.call_args
            assert args[0] == ts.TURNSTILE_VERIFY_URL
            payload = kwargs["data"]
            assert payload["secret"] == "secret-xyz"
            assert payload["response"] == "good-token"
            assert payload["remoteip"] == "1.2.3.4"

    @pytest.mark.asyncio
    async def test_real_mode_failure_returns_false(self):
        client = AsyncMock()
        fail_resp = MagicMock()
        fail_resp.json.return_value = {"success": False, "error-codes": ["invalid-input-response"]}
        client.post.return_value = fail_resp
        deps.http_client = client

        with patch.object(ts, "TURNSTILE_SECRET_KEY", "secret"):
            assert await ts._verify_turnstile("bad-token", source_ip=None) is False

    @pytest.mark.asyncio
    async def test_real_mode_network_error_fails_closed(self):
        client = AsyncMock()
        client.post.side_effect = httpx.HTTPError("connection refused")
        deps.http_client = client

        with patch.object(ts, "TURNSTILE_SECRET_KEY", "secret"):
            assert await ts._verify_turnstile("token", source_ip=None) is False
