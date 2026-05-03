"""License router: status + activation endpoints for the Scutum trial/paid license."""

import logging
from typing import Any, Dict

import deps
import license as license_module
from audit import log_audit_event
from auth import UserInfo, require_admin
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()


class ActivateRequest(BaseModel):
    license_key: str = Field(..., min_length=20, description="The signed JWT we issued you")


@router.get("/license")
async def get_license_status() -> Dict[str, Any]:
    """Public — no auth. The activation page on a fresh deploy needs to read this
    before the customer has admin credentials. Returns no signing material.
    """
    return license_module.current_state().to_public_dict()


@router.post("/license/activate")
async def activate_license(
    payload: ActivateRequest,
    request: Request,
    user: UserInfo = Depends(require_admin),
) -> Dict[str, Any]:
    """Validate a license JWT against the bundled public key, persist it, and
    swap it in as the operative license without a restart.
    """
    state = await license_module.activate(
        payload.license_key,
        deps.db_pool,
        activated_by=f"admin:{user.user_id or user.email or 'unknown'}",
    )

    if not state.is_valid:
        raise HTTPException(status_code=400, detail=state.error or "license invalid")
    if state.is_expired:
        raise HTTPException(status_code=400, detail=state.error or "license already expired")

    await log_audit_event(
        actor_id=user.user_id or "",
        action="license.activate",
        resource_type="license",
        resource_id=state.customer_id,
        resource_name=state.customer_email,
        changes={
            "tier": state.tier,
            "expires_at": state.expires_at.isoformat() if state.expires_at else None,
        },
        request=request,
    )

    return state.to_public_dict()
