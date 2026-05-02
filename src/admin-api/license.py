"""License validation for Scutum self-hosted deploys.

Validates Ed25519-signed JWT license tokens against the bundled public key.
Source priority on startup: explicit JWT passed in -> LICENSE_KEY env var ->
most-recent active row in `licenses` table -> none (operates in pre-trial
limbo for 24h, then degrades to expired state).

Soft-fail design: an expired or missing license never crashes admin-api.
Endpoints keep working; UI shows a renewal banner via /api/v1/license.
Hard feature gates per tier are deferred to v2 once we observe how trials
convert.

The public key sits at `config/license-public.pem` in the repo. The
matching private key lives ONLY on the issuer's laptop (~/.scutum/) and
is never committed. `scripts/issue-license.py` is the local CLI that
mints license tokens.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import jwt as pyjwt

logger = logging.getLogger(__name__)

JWT_ALGORITHM = "EdDSA"
PUBLIC_KEY_PATH = os.getenv(
    "LICENSE_PUBLIC_KEY_PATH",
    str(Path(__file__).resolve().parent.parent.parent / "config" / "license-public.pem"),
)
REVALIDATE_INTERVAL_SECONDS = 300  # 5 minutes


@dataclass
class LicenseState:
    """In-memory representation of the operative license."""

    is_present: bool = False
    is_valid: bool = False
    is_expired: bool = False
    customer_id: str = ""
    customer_email: str = ""
    company: str = ""
    tier: str = ""
    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    days_remaining: int = 0
    features: dict = field(default_factory=dict)
    error: str = ""

    def feature_enabled(self, name: str) -> bool:
        """v1: returns True for any present-and-not-expired license. v2 will tier-gate."""
        return self.is_valid and not self.is_expired and bool(self.features.get(name, True))

    def to_public_dict(self) -> dict[str, Any]:
        """Safe to expose via /api/v1/license — no signing material, no PII beyond email."""
        return {
            "present": self.is_present,
            "valid": self.is_valid,
            "expired": self.is_expired,
            "tier": self.tier or None,
            "customer_email": self.customer_email or None,
            "company": self.company or None,
            "issued_at": self.issued_at.isoformat() if self.issued_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "days_remaining": self.days_remaining,
            "features": self.features,
            "error": self.error or None,
        }


_state: LicenseState = LicenseState()
_public_key_cache: Optional[bytes] = None


def _load_public_key() -> Optional[bytes]:
    global _public_key_cache
    if _public_key_cache is not None:
        return _public_key_cache
    try:
        with open(PUBLIC_KEY_PATH, "rb") as f:
            _public_key_cache = f.read()
        return _public_key_cache
    except FileNotFoundError:
        logger.error(
            "License public key missing at %s. Did you delete config/license-public.pem? "
            "Without it admin-api cannot verify any license — running in unlicensed mode.",
            PUBLIC_KEY_PATH,
        )
        return None


def parse_and_verify(token: str) -> LicenseState:
    """Verify a single JWT against the bundled public key. Returns a populated
    LicenseState whether the token is valid, expired, or malformed.
    """
    state = LicenseState(is_present=True)
    public_key = _load_public_key()
    if public_key is None:
        state.error = "license public key not bundled with admin-api build"
        return state

    try:
        # Disable exp auto-rejection so we can distinguish "expired" from "invalid".
        claims = pyjwt.decode(
            token,
            public_key,
            algorithms=[JWT_ALGORITHM],
            options={"verify_exp": False, "require": ["exp", "iat", "tier", "sub", "email"]},
        )
    except pyjwt.InvalidSignatureError:
        state.error = "license signature does not match — wrong issuer or tampered token"
        return state
    except pyjwt.MissingRequiredClaimError as e:
        state.error = f"license missing required claim: {e}"
        return state
    except pyjwt.DecodeError as e:
        state.error = f"license could not be decoded: {e}"
        return state
    except Exception as e:
        state.error = f"license verification failed: {type(e).__name__}: {e}"
        return state

    state.is_valid = True
    state.customer_id = str(claims.get("sub", ""))
    state.customer_email = str(claims.get("email", ""))
    state.company = str(claims.get("company", ""))
    state.tier = str(claims.get("tier", ""))
    state.features = dict(claims.get("features", {}))

    iat = claims.get("iat")
    exp = claims.get("exp")
    if iat:
        state.issued_at = datetime.fromtimestamp(int(iat), tz=timezone.utc)
    if exp:
        state.expires_at = datetime.fromtimestamp(int(exp), tz=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = state.expires_at - now
        state.days_remaining = max(0, delta.days)
        state.is_expired = delta.total_seconds() <= 0
        if state.is_expired:
            state.error = f"license expired {(-delta).days} day(s) ago"

    return state


async def _load_from_db(db_pool) -> Optional[str]:
    """Return the most-recent active license_key from the DB, or None."""
    if db_pool is None:
        return None
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT license_key
                FROM licenses
                WHERE is_active = TRUE
                ORDER BY expires_at DESC, created_at DESC
                LIMIT 1
                """
            )
            return row["license_key"] if row else None
    except Exception as e:
        logger.warning("Could not read license from DB: %s", e)
        return None


async def _persist(state: LicenseState, token: str, db_pool, activated_by: str = "startup") -> None:
    """Insert a validated license into the licenses table (idempotent on token)."""
    if db_pool is None or not state.is_valid:
        return
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO licenses (
                    license_key, customer_id, customer_email, company, tier,
                    issued_at, expires_at, features, is_active, activated_by
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, TRUE, $9)
                ON CONFLICT (license_key) DO UPDATE
                SET is_active = TRUE
                """,
                token,
                state.customer_id,
                state.customer_email,
                state.company,
                state.tier,
                state.issued_at,
                state.expires_at,
                json.dumps(state.features),
                activated_by,
            )
    except Exception as e:
        logger.warning("Could not persist license: %s", e)


async def initial_load(db_pool) -> LicenseState:
    """Called once during admin-api lifespan startup. Resolves the operative
    license from env -> DB -> none.
    """
    global _state
    env_token = os.getenv("LICENSE_KEY", "").strip()
    db_token = await _load_from_db(db_pool)

    # Env wins on cold-boot (customer is activating); DB wins on warm restarts.
    token = env_token or db_token
    if not token:
        _state = LicenseState()
        logger.warning(
            "No license present (neither LICENSE_KEY env var nor licenses table). "
            "Running in unlicensed mode — UI will show activation prompt."
        )
        return _state

    new_state = parse_and_verify(token)
    if new_state.is_valid and not new_state.is_expired and token == env_token:
        # Activated via env on this boot; persist so future restarts read from DB.
        await _persist(new_state, token, db_pool, activated_by="env:LICENSE_KEY")

    _state = new_state
    if _state.is_valid and not _state.is_expired:
        logger.info(
            "License OK — tier=%s customer=%s expires=%s (%d days left)",
            _state.tier,
            _state.customer_email,
            _state.expires_at.date() if _state.expires_at else "n/a",
            _state.days_remaining,
        )
    else:
        logger.warning("License problem: %s", _state.error or "unknown")
    return _state


async def activate(token: str, db_pool, activated_by: str = "api") -> LicenseState:
    """Validate + persist a token (used by POST /api/v1/license/activate)."""
    global _state
    state = parse_and_verify(token)
    if state.is_valid and not state.is_expired:
        await _persist(state, token, db_pool, activated_by=activated_by)
        _state = state
    return state


def current_state() -> LicenseState:
    return _state


async def revalidator(db_pool, shutdown_event: asyncio.Event) -> None:
    """Background task: re-checks the operative license every 5 min so an
    expiry rollover or a new activation propagates without a restart.
    """
    while not shutdown_event.is_set():
        try:
            await initial_load(db_pool)
        except Exception as e:
            logger.warning("License revalidation error: %s", e)
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=REVALIDATE_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            pass
