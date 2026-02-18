"""SSO authentication flow endpoints (OIDC Authorization Code + PKCE).

These are registered directly in main.py (not as a router) to handle
/auth/sso/* paths alongside the existing /auth/login endpoint.

Flow:
  1. GET /auth/sso/providers         → list available IdPs
  2. GET /auth/sso/authorize/{slug}  → redirect user to IdP
  3. GET /auth/sso/callback          → IdP redirects back, exchange code, issue JWT
"""

import hashlib
import json
import logging
import os
import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import deps
import jwt as pyjwt
from auth import JWT_ALGORITHM, JWT_EXPIRATION_HOURS, JWT_SECRET_KEY
from crypto import decrypt_value
from fastapi import HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SSO_CALLBACK_URL = os.getenv("SSO_CALLBACK_URL", "http://localhost:8086/auth/sso/callback")
SSO_UI_REDIRECT_URL = os.getenv("SSO_UI_REDIRECT_URL", "http://localhost:5173/auth/sso/complete")
SSO_STATE_TTL_SECONDS = 600  # 10 minutes


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class SSOProvider(BaseModel):
    org_slug: str
    org_name: str
    provider_type: str
    provider_name: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate_pkce() -> tuple[str, str]:
    """Generate PKCE code_verifier and code_challenge (S256)."""
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    # base64url-encode without padding
    import base64

    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


async def _store_state(state: str, data: dict) -> None:
    """Store SSO state in Redis (or fall back to in-memory if Redis unavailable)."""
    payload = json.dumps(data)
    if deps.redis_client:
        await deps.redis_client.setex(f"sso_state:{state}", SSO_STATE_TTL_SECONDS, payload)
    else:
        # In-memory fallback (not safe for multi-process, but works for dev)
        _state_store[state] = payload


async def _get_state(state: str) -> Optional[dict]:
    """Retrieve and delete SSO state from Redis."""
    if deps.redis_client:
        key = f"sso_state:{state}"
        payload = await deps.redis_client.get(key)
        if payload:
            await deps.redis_client.delete(key)
            return json.loads(payload)
    else:
        payload = _state_store.pop(state, None)
        if payload:
            return json.loads(payload)
    return None


# In-memory fallback for dev environments without Redis
_state_store: dict = {}


def _get_client_secret(row) -> Optional[str]:
    """Decrypt the stored client secret, or return raw if decryption fails."""
    encrypted = row.get("client_secret_encrypted") or row["client_secret_encrypted"]
    if not encrypted:
        return None
    try:
        return decrypt_value(encrypted)
    except Exception:
        # Might be stored unencrypted (dev mode fallback)
        return encrypted


async def _discover_oidc_config(issuer_url: str) -> dict:
    """Fetch OIDC discovery document from the issuer."""
    if not deps.http_client:
        raise HTTPException(status_code=503, detail="HTTP client not available")

    discovery_url = issuer_url.rstrip("/") + "/.well-known/openid-configuration"
    try:
        resp = await deps.http_client.get(discovery_url, timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error("OIDC discovery failed for %s: %s", issuer_url, e)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch OIDC discovery document from {issuer_url}",
        )


async def _exchange_code_for_tokens(
    token_url: str,
    code: str,
    client_id: str,
    client_secret: Optional[str],
    redirect_uri: str,
    code_verifier: str,
) -> dict:
    """Exchange authorization code for tokens at the IdP token endpoint."""
    if not deps.http_client:
        raise HTTPException(status_code=503, detail="HTTP client not available")

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": code_verifier,
    }
    if client_secret:
        data["client_secret"] = client_secret

    try:
        resp = await deps.http_client.post(
            token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15.0,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error("Token exchange failed at %s: %s", token_url, e)
        raise HTTPException(status_code=502, detail=f"Token exchange failed: {str(e)}")


async def _fetch_userinfo(userinfo_url: str, access_token: str) -> dict:
    """Fetch user info from the IdP userinfo endpoint."""
    if not deps.http_client:
        return {}

    try:
        resp = await deps.http_client.get(
            userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning("Userinfo fetch failed: %s", e)
        return {}


def _decode_id_token_unverified(id_token: str) -> dict:
    """Decode an ID token WITHOUT signature verification.

    For production with proper JWKS verification, use authlib or pyjwt with
    the IdP's public keys. This is sufficient when the token was just received
    directly from the IdP token endpoint over HTTPS.
    """
    return pyjwt.decode(id_token, options={"verify_signature": False})


async def _upsert_user(
    external_id: str,
    email: str,
    display_name: Optional[str],
    auth_provider: str,
    idp_metadata: dict,
) -> dict:
    """Create or update a user in the local users table. Returns user row as dict."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO users (email, display_name, auth_provider, external_id, idp_metadata, last_login_at)
            VALUES ($1, $2, $3, $4, $5::jsonb, CURRENT_TIMESTAMP)
            ON CONFLICT (auth_provider, external_id) WHERE external_id IS NOT NULL
            DO UPDATE SET
                email = EXCLUDED.email,
                display_name = COALESCE(EXCLUDED.display_name, users.display_name),
                idp_metadata = EXCLUDED.idp_metadata,
                last_login_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            RETURNING *
            """,
            email,
            display_name,
            auth_provider,
            external_id,
            json.dumps(idp_metadata),
        )
        return dict(row) if row else {}


async def _apply_group_mapping(user_id: str, org_id: str, groups: list, group_to_org_mapping: dict) -> dict:
    """Map IdP groups to org roles using the SSO config's group_to_org_mapping.

    group_to_org_mapping format: {"idp-group-name": "org_role", "admins": "org_admin", ...}
    """
    if not deps.db_pool or not groups or not group_to_org_mapping:
        return {}

    roles_assigned = {}

    async with deps.db_pool.acquire() as conn:
        for group in groups:
            role = group_to_org_mapping.get(group)
            if not role:
                # Try wildcard
                role = group_to_org_mapping.get("*", "member")

            if role:
                await conn.execute(
                    """
                    INSERT INTO org_memberships (user_id, org_id, role)
                    VALUES ($1::uuid, $2::uuid, $3)
                    ON CONFLICT (user_id, org_id, bu_id) DO UPDATE SET role = $3
                    """,
                    user_id,
                    org_id,
                    role,
                )
                roles_assigned[group] = role

    return roles_assigned


# ---------------------------------------------------------------------------
# Public API functions (registered in main.py)
# ---------------------------------------------------------------------------


async def list_sso_providers() -> List[SSOProvider]:
    """List available SSO providers across all organizations."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT o.slug AS org_slug, o.name AS org_name,
                   s.provider_type, s.provider_name
            FROM sso_configs s
            JOIN organizations o ON o.id = s.org_id
            WHERE s.is_active = TRUE AND o.is_active = TRUE
            ORDER BY o.name
        """)
        return [
            SSOProvider(
                org_slug=row["org_slug"],
                org_name=row["org_name"],
                provider_type=row["provider_type"],
                provider_name=row["provider_name"],
            )
            for row in rows
        ]


async def sso_authorize(org_slug: str):
    """Redirect user to the IdP authorization endpoint.

    Builds an OIDC Authorization Code + PKCE request and redirects the user
    to the identity provider. State and PKCE verifier are stored in Redis.
    """
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT s.*, o.id AS oid, o.slug
            FROM sso_configs s
            JOIN organizations o ON o.id = s.org_id
            WHERE o.slug = $1 AND s.is_active = TRUE
            LIMIT 1
            """,
            org_slug,
        )

    if not row:
        raise HTTPException(status_code=404, detail="SSO not configured for this organization")

    if row["provider_type"] not in ("oidc", "okta", "azure_ad", "google_workspace"):
        raise HTTPException(
            status_code=400,
            detail=f"SSO provider type '{row['provider_type']}' is not yet supported for login flow. Only OIDC-based providers are supported.",
        )

    # Resolve OIDC endpoints
    authorization_url = row["authorization_url"]
    token_url = row["token_url"]
    userinfo_url = row["userinfo_url"]

    if row["issuer_url"] and (not authorization_url or not token_url):
        # Use OIDC discovery to fill in missing endpoints
        discovery = await _discover_oidc_config(row["issuer_url"])
        authorization_url = authorization_url or discovery.get("authorization_endpoint")
        token_url = token_url or discovery.get("token_endpoint")
        userinfo_url = userinfo_url or discovery.get("userinfo_endpoint")

    if not authorization_url:
        raise HTTPException(
            status_code=400,
            detail="SSO authorization URL not configured and could not be discovered",
        )

    if not row["client_id"]:
        raise HTTPException(status_code=400, detail="SSO client_id not configured")

    # Generate PKCE and state
    code_verifier, code_challenge = _generate_pkce()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(16)

    # Store state in Redis for callback validation
    await _store_state(
        state,
        {
            "org_slug": org_slug,
            "org_id": str(row["oid"]),
            "sso_config_id": str(row["id"]),
            "code_verifier": code_verifier,
            "nonce": nonce,
            "client_id": row["client_id"],
            "token_url": token_url,
            "userinfo_url": userinfo_url,
            "scopes": row["scopes"] or "openid email profile",
            "group_claim": row["group_claim"] or "groups",
            "group_to_org_mapping": json.loads(row["group_to_org_mapping"])
            if isinstance(row["group_to_org_mapping"], str)
            else (row["group_to_org_mapping"] or {}),
            "provider_type": row["provider_type"],
        },
    )

    # Build authorization URL
    scopes = row["scopes"] or "openid email profile"
    params = {
        "response_type": "code",
        "client_id": row["client_id"],
        "redirect_uri": SSO_CALLBACK_URL,
        "scope": scopes,
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    auth_redirect = f"{authorization_url}?{urllib.parse.urlencode(params)}"
    logger.info("SSO authorize redirect for org %s to %s", org_slug, authorization_url)
    return RedirectResponse(url=auth_redirect)


async def sso_callback(
    code: str = Query(default=""),
    state: str = Query(default=""),
):
    """Handle OIDC callback from IdP.

    1. Validate state (anti-CSRF)
    2. Exchange authorization code for tokens (with PKCE verifier)
    3. Decode ID token to extract user claims
    4. Optionally fetch userinfo for additional claims
    5. Upsert user in local DB
    6. Apply group-to-org role mapping
    7. Issue JWT and redirect to frontend
    """
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    if not state:
        raise HTTPException(status_code=400, detail="Missing state parameter")

    # Retrieve and validate state
    state_data = await _get_state(state)
    if not state_data:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired SSO state. Please try logging in again.",
        )

    token_url = state_data["token_url"]
    if not token_url:
        raise HTTPException(status_code=500, detail="Token URL not available in SSO state")

    # Get client secret from DB
    client_secret = None
    if deps.db_pool:
        async with deps.db_pool.acquire() as conn:
            sso_row = await conn.fetchrow(
                "SELECT client_secret_encrypted FROM sso_configs WHERE id = $1::uuid",
                state_data["sso_config_id"],
            )
            if sso_row:
                client_secret = _get_client_secret(sso_row)

    # Exchange code for tokens
    token_response = await _exchange_code_for_tokens(
        token_url=token_url,
        code=code,
        client_id=state_data["client_id"],
        client_secret=client_secret,
        redirect_uri=SSO_CALLBACK_URL,
        code_verifier=state_data["code_verifier"],
    )

    access_token = token_response.get("access_token")
    id_token = token_response.get("id_token")

    if not id_token and not access_token:
        raise HTTPException(status_code=502, detail="IdP returned no tokens")

    # Extract user info from ID token
    user_claims = {}
    if id_token:
        try:
            user_claims = _decode_id_token_unverified(id_token)
        except Exception as e:
            logger.warning("Failed to decode ID token: %s", e)

    # Supplement with userinfo endpoint if available
    userinfo_url = state_data.get("userinfo_url")
    if userinfo_url and access_token:
        userinfo = await _fetch_userinfo(userinfo_url, access_token)
        # Merge (userinfo takes precedence for profile fields)
        user_claims = {**user_claims, **userinfo}

    # Extract key fields
    external_id = user_claims.get("sub", "")
    email = user_claims.get("email", "")
    display_name = user_claims.get("name") or user_claims.get("preferred_username")
    groups = user_claims.get(state_data.get("group_claim", "groups"), [])
    if isinstance(groups, str):
        groups = [groups]

    if not external_id:
        raise HTTPException(status_code=502, detail="IdP did not return a 'sub' claim")
    if not email:
        # Some IdPs don't return email in the ID token
        email = f"{external_id}@sso"

    # Upsert user in local DB
    user_row = await _upsert_user(
        external_id=external_id,
        email=email,
        display_name=display_name,
        auth_provider=state_data.get("provider_type", "oidc"),
        idp_metadata={
            "groups": groups,
            "provider": state_data.get("provider_type"),
            "org_slug": state_data["org_slug"],
        },
    )

    user_id = str(user_row.get("id", external_id))
    org_id = state_data["org_id"]
    is_platform_admin = user_row.get("is_platform_admin", False)

    # Apply group mapping
    org_roles = {}
    group_mapping = state_data.get("group_to_org_mapping", {})
    if groups and group_mapping:
        org_roles = await _apply_group_mapping(user_id, org_id, groups, group_mapping)
    else:
        # Default: add as member if no group mapping configured
        if deps.db_pool:
            try:
                async with deps.db_pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO org_memberships (user_id, org_id, role)
                        VALUES ($1::uuid, $2::uuid, 'member')
                        ON CONFLICT (user_id, org_id, bu_id) DO NOTHING
                        """,
                        user_id,
                        org_id,
                    )
            except Exception as e:
                logger.warning("Failed to create default org membership: %s", e)

    # Determine effective role
    is_admin = is_platform_admin or "org_admin" in org_roles.values()
    role = "admin" if is_admin else "user"

    # Issue JWT
    expires_at = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    jwt_payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "is_admin": is_admin,
        "is_platform_admin": is_platform_admin,
        "org_id": org_id,
        "org_roles": org_roles,
        "exp": expires_at,
        "iat": datetime.now(timezone.utc),
    }

    token = pyjwt.encode(jwt_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    logger.info(
        "SSO login successful: user=%s email=%s org=%s provider=%s",
        user_id,
        email,
        state_data["org_slug"],
        state_data.get("provider_type"),
    )

    # Redirect to frontend with token
    redirect_url = f"{SSO_UI_REDIRECT_URL}?token={token}&expires_at={expires_at.isoformat()}"
    return RedirectResponse(url=redirect_url)
