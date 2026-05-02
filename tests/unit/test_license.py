"""Unit tests for the Scutum license validator.

Covers: signature verification, expiry detection, tampering, wrong-issuer
rejection, missing-claim rejection, and the public-shape of LicenseState.

Tests do NOT require a database — they exercise `parse_and_verify` directly
with tokens signed by the repo's bundled keypair (the issuer's private key
must live at ~/.scutum/license-private.pem on the developer's laptop).
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ADMIN_API = REPO_ROOT / "src" / "admin-api"
ISSUER_PRIVATE_KEY = Path(os.path.expanduser("~/.scutum/license-private.pem"))
ISSUE_SCRIPT = REPO_ROOT / "scripts" / "issue-license.py"

sys.path.insert(0, str(ADMIN_API))

# Skip every test in this module if the issuer's private key isn't on this machine
# (so CI without secrets doesn't fail; integration env can opt in).
pytestmark = pytest.mark.skipif(
    not ISSUER_PRIVATE_KEY.exists(),
    reason="Issuer private key not present (~/.scutum/license-private.pem). Skipping license tests on this host.",
)


def _issue(email: str = "test@scutum.dev", tier: str = "trial", days: int = 30) -> str:
    out = subprocess.check_output(
        [
            sys.executable,
            str(ISSUE_SCRIPT),
            "--email",
            email,
            "--tier",
            tier,
            "--days",
            str(days),
            "--quiet",
        ]
    )
    return out.decode().strip()


@pytest.fixture(autouse=True)
def _reload_license_module():
    """Each test imports the license module fresh — avoids cached state bleed."""
    import importlib

    import license as license_module

    importlib.reload(license_module)
    yield


def test_valid_trial_round_trips():
    import license as L

    token = _issue(email="alice@acme.com", tier="trial", days=30)
    state = L.parse_and_verify(token)

    assert state.is_present is True
    assert state.is_valid is True
    assert state.is_expired is False
    assert state.tier == "trial"
    assert state.customer_email == "alice@acme.com"
    assert state.customer_id.startswith("cust_")
    assert state.days_remaining == 29  # issuance happens slightly before now
    assert state.error == ""
    assert "max_admins" in state.features


def test_expired_license_marked_expired_not_invalid():
    """An expired but otherwise-valid license must be is_valid=True, is_expired=True.
    The router uses this distinction to surface 'renew' rather than 'invalid'."""
    import license as L

    token = _issue(email="alice@acme.com", tier="trial", days=-1)
    state = L.parse_and_verify(token)

    assert state.is_valid is True
    assert state.is_expired is True
    assert "expired" in state.error.lower()
    assert state.days_remaining == 0


def test_tampered_token_rejected():
    import license as L

    token = _issue()
    tampered = token[:-5] + "ZZZZZ"

    state = L.parse_and_verify(tampered)
    assert state.is_valid is False
    assert "signature" in state.error.lower() or "decoded" in state.error.lower()


def test_wrong_issuer_rejected():
    """Tokens signed by a different Ed25519 key must fail verification."""
    import license as L

    rogue_key = Ed25519PrivateKey.generate().private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    rogue_token = pyjwt.encode(
        {
            "sub": "cust_attacker",
            "email": "x@x.com",
            "tier": "enterprise",
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int((datetime.now(timezone.utc) + timedelta(days=3650)).timestamp()),
        },
        rogue_key,
        algorithm="EdDSA",
    )

    state = L.parse_and_verify(rogue_token)
    assert state.is_valid is False
    assert "signature" in state.error.lower()


def test_missing_required_claim_rejected():
    """Tokens that lack one of {sub, email, tier, iat, exp} are rejected
    even with a valid signature — defense against minted-but-malformed."""
    import license as L

    with open(ISSUER_PRIVATE_KEY, "rb") as f:
        priv = f.read()
    incomplete = pyjwt.encode(
        {
            "sub": "cust_x",
            "tier": "trial",
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp()),
            # email omitted
        },
        priv,
        algorithm="EdDSA",
    )
    state = L.parse_and_verify(incomplete)
    assert state.is_valid is False
    assert "email" in state.error.lower()


def test_to_public_dict_excludes_signing_material():
    """The shape returned to /api/v1/license must NOT contain JWT or key bytes."""
    import license as L

    token = _issue()
    state = L.parse_and_verify(token)
    public = state.to_public_dict()

    serialized = str(public)
    assert token not in serialized, "license JWT must never appear in the public dict"
    assert "BEGIN" not in serialized, "PEM material must never leak"
    assert public["valid"] is True
    assert public["expired"] is False
    assert public["tier"] == "trial"
    assert public["customer_email"]
    assert public["expires_at"]
    assert public["days_remaining"] >= 0


def test_garbage_input_does_not_crash():
    import license as L

    for junk in ["", "not.a.jwt", "x" * 5000, "...", "foo.bar.baz"]:
        state = L.parse_and_verify(junk)
        assert state.is_valid is False
        # No exception bubbled, soft-fail honored
