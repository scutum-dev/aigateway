"""SSO authentication flow endpoints.

These are registered directly in main.py (not as a router) to handle
/auth/sso/* paths alongside the existing /auth/login endpoint.
"""

import logging
import os
from typing import List, Optional

import deps
from auth import JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRATION_HOURS
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Query
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

import jwt as pyjwt

logger = logging.getLogger(__name__)


class SSOProvider(BaseModel):
    org_slug: str
    org_name: str
    provider_type: str
    provider_name: str


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
    """Redirect user to the IdP authorization endpoint (stub).

    In production this would build the OIDC authorization URL
    and redirect the user to the identity provider.
    """
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT s.*, o.id AS oid, o.slug
            FROM sso_configs s
            JOIN organizations o ON o.id = s.org_id
            WHERE o.slug = $1 AND s.is_active = TRUE
            LIMIT 1
        """, org_slug)

    if not row:
        raise HTTPException(status_code=404, detail="SSO not configured for this organization")

    # In production: build redirect to IdP
    # For now, return a stub response with the authorization URL
    auth_url = row["authorization_url"] or row["issuer_url"]
    if auth_url:
        # Stub: in production, this would include state, nonce, redirect_uri, etc.
        return JSONResponse({
            "message": "SSO authorization stub",
            "provider": row["provider_name"],
            "org_slug": org_slug,
            "authorization_url": auth_url,
            "note": "In production, this endpoint would redirect to the IdP",
        })
    else:
        raise HTTPException(
            status_code=400,
            detail="SSO authorization URL not configured",
        )


async def sso_callback(
    code: str = Query(default="stub-code"),
    state: str = Query(default=""),
):
    """Handle OIDC callback from IdP (stub).

    In production this would:
    1. Exchange the authorization code for tokens
    2. Validate the ID token
    3. Extract user info and group claims
    4. Create/update user in the database
    5. Issue a JWT token
    """
    # Stub implementation: create a JWT for a demo SSO user
    # In production, the user info would come from the IdP token exchange
    stub_user = {
        "user_id": "sso-user",
        "email": "sso-user@example.com",
        "role": "user",
        "is_admin": False,
        "auth_provider": "oidc",
    }

    expires_at = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)

    payload = {
        "sub": stub_user["user_id"],
        "email": stub_user["email"],
        "role": stub_user["role"],
        "is_admin": stub_user["is_admin"],
        "is_platform_admin": False,
        "org_id": None,
        "org_roles": {},
        "exp": expires_at,
        "iat": datetime.now(timezone.utc),
    }

    token = pyjwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    # In production, redirect to the frontend with the token
    admin_ui_url = os.getenv("ADMIN_UI_URL", "http://localhost:5173")
    redirect_url = f"{admin_ui_url}/auth/sso/complete?token={token}&expires_at={expires_at.isoformat()}"

    return RedirectResponse(url=redirect_url)
