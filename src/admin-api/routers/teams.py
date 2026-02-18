"""Team management router — proxies to LiteLLM."""

import logging
from typing import Any, Dict, List, Optional

import deps
from auth import UserInfo, get_current_user, require_admin
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)


class TeamCreateRequest(BaseModel):
    team_alias: str
    max_budget: Optional[float] = None
    models: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class TeamUpdateRequest(BaseModel):
    team_id: str
    team_alias: Optional[str] = None
    max_budget: Optional[float] = None
    models: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class TeamDeleteRequest(BaseModel):
    team_ids: List[str]


class TeamMemberAddRequest(BaseModel):
    member: Dict[str, Any]  # {"role": "user", "user_id": "..."}


class TeamMemberDeleteRequest(BaseModel):
    user_id: str


def _litellm_headers() -> dict:
    return {"Authorization": f"Bearer {deps.LITELLM_MASTER_KEY}"}


def _ensure_http():
    if not deps.http_client:
        raise HTTPException(status_code=503, detail="HTTP client not available")


@router.get("/teams")
async def list_teams(user: UserInfo = Depends(get_current_user)):
    """List all teams via LiteLLM."""
    _ensure_http()
    resp = await deps.http_client.get(
        f"{deps.LITELLM_URL}/team/list",
        headers=_litellm_headers(),
    )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@router.post("/teams")
async def create_team(request: TeamCreateRequest, user: UserInfo = Depends(require_admin)):
    """Create a new team via LiteLLM."""
    _ensure_http()
    resp = await deps.http_client.post(
        f"{deps.LITELLM_URL}/team/new",
        json=request.model_dump(exclude_none=True),
        headers=_litellm_headers(),
    )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@router.get("/teams/{team_id}")
async def get_team(team_id: str, user: UserInfo = Depends(get_current_user)):
    """Get a specific team's info via LiteLLM."""
    _ensure_http()
    resp = await deps.http_client.get(
        f"{deps.LITELLM_URL}/team/info",
        params={"team_id": team_id},
        headers=_litellm_headers(),
    )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@router.post("/teams/update")
async def update_team(request: TeamUpdateRequest, user: UserInfo = Depends(require_admin)):
    """Update a team via LiteLLM."""
    _ensure_http()
    resp = await deps.http_client.post(
        f"{deps.LITELLM_URL}/team/update",
        json=request.model_dump(exclude_none=True),
        headers=_litellm_headers(),
    )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@router.post("/teams/delete")
async def delete_team(request: TeamDeleteRequest, user: UserInfo = Depends(require_admin)):
    """Delete team(s) via LiteLLM."""
    _ensure_http()
    resp = await deps.http_client.post(
        f"{deps.LITELLM_URL}/team/delete",
        json=request.model_dump(),
        headers=_litellm_headers(),
    )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@router.post("/teams/{team_id}/members")
async def add_team_member(
    team_id: str,
    request: TeamMemberAddRequest,
    user: UserInfo = Depends(require_admin),
):
    """Add a member to a team via LiteLLM."""
    _ensure_http()
    resp = await deps.http_client.post(
        f"{deps.LITELLM_URL}/team/member_add",
        json={"team_id": team_id, "member": request.member},
        headers=_litellm_headers(),
    )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@router.post("/teams/{team_id}/members/delete")
async def delete_team_member(
    team_id: str,
    request: TeamMemberDeleteRequest,
    user: UserInfo = Depends(require_admin),
):
    """Remove a member from a team via LiteLLM."""
    _ensure_http()
    resp = await deps.http_client.post(
        f"{deps.LITELLM_URL}/team/member_delete",
        json={"team_id": team_id, "user_id": request.user_id},
        headers=_litellm_headers(),
    )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()
