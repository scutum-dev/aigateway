"""Unit tests for the License router.

Covers GET /api/v1/license (public, no auth) and POST /api/v1/license/activate
(admin auth required + license validation). Tightly coupled to license.py
parse_and_verify, so signature/expiry behaviour is exercised through real
JWTs minted with a temporary keypair — not via mocking the validator,
because the validator IS the security-critical code under test.
"""

import importlib
import importlib.util
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

# ---------------------------------------------------------------------------
# Module loading (mirror tests/unit/test_router_audit.py boilerplate)
# ---------------------------------------------------------------------------

_service_dir = os.path.join(os.path.dirname(__file__), "../../src/admin-api")
sys.path.insert(0, _service_dir)

_otel_mock = MagicMock()
for _mod in [
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
    sys.modules.setdefault(_mod, _otel_mock)
sys.modules.setdefault("alembic", MagicMock())
sys.modules.setdefault("alembic.config", MagicMock())
sys.modules.setdefault("alembic.command", MagicMock())


@pytest.fixture(autouse=True)
def _ephemeral_keypair(tmp_path, monkeypatch):
    """Each test gets a fresh Ed25519 keypair. Public key path is injected via
    LICENSE_PUBLIC_KEY_PATH; private key bytes are returned for minting test
    tokens. This keeps tests hermetic — no dependency on whoever's developer
    laptop happens to have ~/.scutum/license-private.pem.
    """
    priv_key = Ed25519PrivateKey.generate()
    pub_pem = priv_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    priv_pem = priv_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    pub_path = tmp_path / "license-public.pem"
    pub_path.write_bytes(pub_pem)
    monkeypatch.setenv("LICENSE_PUBLIC_KEY_PATH", str(pub_path))
    monkeypatch.delenv("LICENSE_KEY", raising=False)

    # Reload license.py so the public-key cache is rebuilt against the new path.
    import license as license_module

    importlib.reload(license_module)

    # Make sure the router test target is enabled — leads-style env gate is
    # only on the leads router; license is unconditional. Still, force-reload
    # main so dependency_overrides setup below sees a clean app.
    if "admin_api_main" in sys.modules:
        del sys.modules["admin_api_main"]
    spec = importlib.util.spec_from_file_location("admin_api_main", os.path.join(_service_dir, "main.py"))
    main_mod = importlib.util.module_from_spec(spec)
    sys.modules["admin_api_main"] = main_mod
    spec.loader.exec_module(main_mod)

    return priv_pem


def _mint(priv_pem, *, email="acme@example.com", tier="trial", days=30, **extra):
    now = datetime.now(timezone.utc)
    claims = {
        "sub": f"cust_{tier}_test",
        "email": email,
        "company": "Test Corp",
        "tier": tier,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=days)).timestamp()),
        "features": {"max_admins": 5, "mcp_servers": True},
        **extra,
    }
    return pyjwt.encode(claims, priv_pem, algorithm="EdDSA")


def _client():
    main_mod = sys.modules["admin_api_main"]
    app = main_mod.app

    from auth import UserInfo, get_current_user, require_admin

    def _fake_admin():
        return UserInfo(user_id="test-admin", role="admin", is_admin=True)

    app.dependency_overrides[get_current_user] = _fake_admin
    app.dependency_overrides[require_admin] = _fake_admin
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def _mock_pool():
    """db_pool that swallows persists silently — they're not what these
    tests are exercising. Validation runs against the public key only."""
    import deps

    conn = AsyncMock()
    conn.fetchrow.return_value = None
    conn.fetchval.return_value = None
    conn.execute.return_value = "INSERT 0 1"
    conn.fetch.return_value = []
    pool = MagicMock()
    ctx = AsyncMock()
    ctx.__aenter__.return_value = conn
    ctx.__aexit__.return_value = None
    pool.acquire.return_value = ctx
    deps.db_pool = pool
    return pool


# ===========================================================================
# GET /api/v1/license — public, no auth required
# ===========================================================================


@pytest.mark.asyncio
async def test_license_status_no_license_present():
    """When no license is loaded, endpoint returns valid:false with present:false."""
    _mock_pool()
    async with _client() as c:
        r = await c.get("/api/v1/license")
    assert r.status_code == 200
    body = r.json()
    assert body["present"] is False
    assert body["valid"] is False
    assert body["tier"] is None


@pytest.mark.asyncio
async def test_license_status_endpoint_is_public():
    """The status endpoint must work without admin credentials so a fresh
    deploy can render an activation prompt before the operator has logged in."""
    main_mod = sys.modules["admin_api_main"]
    app = main_mod.app

    # Strip any auth overrides — simulate the unauth case
    app.dependency_overrides.clear()

    _mock_pool()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/license")
    assert r.status_code == 200, "license status must not require auth"


# ===========================================================================
# POST /api/v1/license/activate
# ===========================================================================


@pytest.mark.asyncio
async def test_activate_valid_jwt_swaps_state(_ephemeral_keypair):
    """Posting a freshly-minted valid JWT should swap the operative license
    in-memory and return the new state."""
    _mock_pool()
    token = _mint(_ephemeral_keypair, tier="business", days=365)

    async with _client() as c:
        r = await c.post("/api/v1/license/activate", json={"license_key": token})

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["valid"] is True
    assert body["expired"] is False
    assert body["tier"] == "business"
    assert body["customer_email"] == "acme@example.com"
    assert body["days_remaining"] >= 364

    import license as license_module

    assert license_module.current_state().tier == "business"


@pytest.mark.asyncio
async def test_activate_expired_jwt_rejected(_ephemeral_keypair):
    """Expired-but-validly-signed token must NOT activate. Router returns 400."""
    _mock_pool()
    token = _mint(_ephemeral_keypair, days=-1)

    async with _client() as c:
        r = await c.post("/api/v1/license/activate", json={"license_key": token})

    assert r.status_code == 400
    detail = r.json()["detail"].lower()
    assert "expired" in detail


@pytest.mark.asyncio
async def test_activate_tampered_jwt_rejected(_ephemeral_keypair):
    """Token with valid format but bad signature must be rejected."""
    _mock_pool()
    token = _mint(_ephemeral_keypair) + "TAMPERED"

    async with _client() as c:
        r = await c.post("/api/v1/license/activate", json={"license_key": token})

    assert r.status_code == 400
    assert "signature" in r.json()["detail"].lower() or "decoded" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_activate_wrong_issuer_rejected(_ephemeral_keypair):
    """Token signed by a different Ed25519 keypair (i.e., not by us) must
    be rejected even if every claim is otherwise well-formed."""
    rogue_priv = Ed25519PrivateKey.generate().private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    now = datetime.now(timezone.utc)
    rogue_token = pyjwt.encode(
        {
            "sub": "cust_attacker",
            "email": "attacker@evil.com",
            "tier": "enterprise",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(days=3650)).timestamp()),
        },
        rogue_priv,
        algorithm="EdDSA",
    )

    _mock_pool()
    async with _client() as c:
        r = await c.post("/api/v1/license/activate", json={"license_key": rogue_token})

    assert r.status_code == 400
    assert "signature" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_activate_too_short_payload_rejected_by_validator():
    """Pydantic min_length=20 on the request body should reject empty / short
    payloads BEFORE they reach the JWT validator. Defends against trivial
    DoS via expensive parse attempts on garbage input."""
    _mock_pool()
    async with _client() as c:
        r = await c.post("/api/v1/license/activate", json={"license_key": "abc"})
    assert r.status_code == 422  # Pydantic ValidationError


@pytest.mark.asyncio
async def test_activate_response_omits_signing_material(_ephemeral_keypair):
    """Whatever the response body contains, it must NOT include the JWT or
    any PEM bytes — those would be a credential leak via /license endpoint."""
    _mock_pool()
    token = _mint(_ephemeral_keypair)

    async with _client() as c:
        r = await c.post("/api/v1/license/activate", json={"license_key": token})

    body_str = json.dumps(r.json())
    assert token not in body_str, "license JWT must not appear in activate response"
    assert "BEGIN" not in body_str, "PEM material must never leak"
