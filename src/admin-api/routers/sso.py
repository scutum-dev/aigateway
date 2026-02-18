"""SSO configuration management router."""

import json
import logging
from typing import List, Optional

import deps
from audit import log_audit_event
from auth import UserInfo, get_current_user, require_admin
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class SSOConfigCreate(BaseModel):
    provider_type: str
    provider_name: str
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    issuer_url: Optional[str] = None
    authorization_url: Optional[str] = None
    token_url: Optional[str] = None
    userinfo_url: Optional[str] = None
    jwks_uri: Optional[str] = None
    saml_metadata_url: Optional[str] = None
    scopes: Optional[str] = "openid email profile"
    group_claim: Optional[str] = "groups"
    group_to_org_mapping: Optional[dict] = None
    is_active: bool = True


class SSOConfig(BaseModel):
    id: str
    org_id: str
    provider_type: str
    provider_name: str
    client_id: Optional[str] = None
    issuer_url: Optional[str] = None
    authorization_url: Optional[str] = None
    token_url: Optional[str] = None
    userinfo_url: Optional[str] = None
    jwks_uri: Optional[str] = None
    saml_metadata_url: Optional[str] = None
    scopes: Optional[str] = None
    group_claim: Optional[str] = None
    group_to_org_mapping: dict = {}
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SSOTestResult(BaseModel):
    status: str
    message: str
    details: dict = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_sso(row) -> SSOConfig:
    mapping = row["group_to_org_mapping"]
    if isinstance(mapping, str):
        mapping = json.loads(mapping)
    return SSOConfig(
        id=str(row["id"]),
        org_id=str(row["org_id"]),
        provider_type=row["provider_type"],
        provider_name=row["provider_name"],
        client_id=row["client_id"],
        issuer_url=row["issuer_url"],
        authorization_url=row["authorization_url"],
        token_url=row["token_url"],
        userinfo_url=row["userinfo_url"],
        jwks_uri=row["jwks_uri"],
        saml_metadata_url=row["saml_metadata_url"],
        scopes=row["scopes"],
        group_claim=row["group_claim"],
        group_to_org_mapping=mapping if isinstance(mapping, dict) else {},
        is_active=row["is_active"],
        created_at=str(row["created_at"]) if row["created_at"] else None,
        updated_at=str(row["updated_at"]) if row["updated_at"] else None,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/organizations/{org_id}/sso", response_model=SSOConfig)
async def get_sso_config(org_id: str, user: UserInfo = Depends(get_current_user)):
    """Get SSO configuration for an organization."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM sso_configs WHERE org_id = $1 AND is_active = TRUE LIMIT 1", org_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="SSO config not found")
        return _row_to_sso(row)


@router.post("/organizations/{org_id}/sso", response_model=SSOConfig)
async def create_or_update_sso_config(
    org_id: str,
    data: SSOConfigCreate,
    request: Request,
    user: UserInfo = Depends(require_admin),
):
    """Create or update SSO configuration for an organization."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    # Encrypt client secret if provided
    client_secret_encrypted = None
    if data.client_secret:
        try:
            from crypto import encrypt_value
            client_secret_encrypted = encrypt_value(data.client_secret)
        except ValueError:
            # SSO_ENCRYPTION_KEY not configured, store as-is with a warning
            logger.warning("SSO_ENCRYPTION_KEY not configured, storing client secret unencrypted")
            client_secret_encrypted = data.client_secret

    group_mapping = json.dumps(data.group_to_org_mapping or {})

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO sso_configs (org_id, provider_type, provider_name, client_id,
                client_secret_encrypted, issuer_url, authorization_url, token_url,
                userinfo_url, jwks_uri, saml_metadata_url, scopes, group_claim,
                group_to_org_mapping, is_active)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
            ON CONFLICT (org_id, provider_type) DO UPDATE SET
                provider_name = EXCLUDED.provider_name,
                client_id = EXCLUDED.client_id,
                client_secret_encrypted = EXCLUDED.client_secret_encrypted,
                issuer_url = EXCLUDED.issuer_url,
                authorization_url = EXCLUDED.authorization_url,
                token_url = EXCLUDED.token_url,
                userinfo_url = EXCLUDED.userinfo_url,
                jwks_uri = EXCLUDED.jwks_uri,
                saml_metadata_url = EXCLUDED.saml_metadata_url,
                scopes = EXCLUDED.scopes,
                group_claim = EXCLUDED.group_claim,
                group_to_org_mapping = EXCLUDED.group_to_org_mapping,
                is_active = EXCLUDED.is_active,
                updated_at = CURRENT_TIMESTAMP
            RETURNING *
            """,
            org_id,
            data.provider_type,
            data.provider_name,
            data.client_id,
            client_secret_encrypted,
            data.issuer_url,
            data.authorization_url,
            data.token_url,
            data.userinfo_url,
            data.jwks_uri,
            data.saml_metadata_url,
            data.scopes,
            data.group_claim,
            group_mapping,
            data.is_active,
        )
        sso = _row_to_sso(row)
        await log_audit_event(
            actor_id=user.user_id,
            action="configure_sso",
            resource_type="sso_config",
            resource_id=sso.id,
            org_id=org_id,
            request=request,
        )
        return sso


@router.delete("/organizations/{org_id}/sso")
async def disable_sso(
    org_id: str,
    request: Request,
    user: UserInfo = Depends(require_admin),
):
    """Disable SSO for an organization."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE sso_configs SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP WHERE org_id = $1",
            org_id,
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="SSO config not found")

    await log_audit_event(
        actor_id=user.user_id,
        action="disable_sso",
        resource_type="sso_config",
        org_id=org_id,
        request=request,
    )
    return {"status": "disabled"}


@router.post("/organizations/{org_id}/sso/test", response_model=SSOTestResult)
async def test_sso_connection(
    org_id: str,
    user: UserInfo = Depends(require_admin),
):
    """Test SSO connection for an organization (mock test)."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM sso_configs WHERE org_id = $1 AND is_active = TRUE LIMIT 1", org_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="SSO config not found")

    # Mock test — in production this would attempt to connect to the IdP
    has_issuer = bool(row["issuer_url"])
    has_client = bool(row["client_id"])

    if has_issuer and has_client:
        return SSOTestResult(
            status="ok",
            message=f"SSO configuration for {row['provider_name']} appears valid",
            details={
                "provider_type": row["provider_type"],
                "issuer_url": row["issuer_url"],
                "has_client_id": True,
                "has_client_secret": bool(row["client_secret_encrypted"]),
            },
        )
    else:
        return SSOTestResult(
            status="warning",
            message="SSO configuration is incomplete",
            details={
                "has_issuer_url": has_issuer,
                "has_client_id": has_client,
            },
        )
