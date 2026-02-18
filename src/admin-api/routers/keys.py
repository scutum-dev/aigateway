"""API Key management router — proxies to LiteLLM."""

import logging

import deps
from auth import UserInfo, get_current_user, require_admin
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

router = APIRouter()
logger = logging.getLogger(__name__)


class KeyGenerateRequest(BaseModel):
    key_alias: Optional[str] = None
    max_budget: Optional[float] = None
    models: Optional[List[str]] = None
    team_id: Optional[str] = None
    duration: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class KeyUpdateRequest(BaseModel):
    key: str
    key_alias: Optional[str] = None
    max_budget: Optional[float] = None
    models: Optional[List[str]] = None
    duration: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class KeyDeleteRequest(BaseModel):
    keys: List[str]


def _litellm_headers() -> dict:
    return {"Authorization": f"Bearer {deps.LITELLM_MASTER_KEY}"}


def _ensure_http():
    if not deps.http_client:
        raise HTTPException(status_code=503, detail="HTTP client not available")


@router.post("/keys/generate")
async def generate_key(request: KeyGenerateRequest, user: UserInfo = Depends(require_admin)):
    """Generate a new API key via LiteLLM."""
    _ensure_http()
    resp = await deps.http_client.post(
        f"{deps.LITELLM_URL}/key/generate",
        json=request.model_dump(exclude_none=True),
        headers=_litellm_headers(),
    )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@router.get("/keys")
async def list_keys(user: UserInfo = Depends(get_current_user)):
    """List all API keys via LiteLLM."""
    _ensure_http()
    resp = await deps.http_client.get(
        f"{deps.LITELLM_URL}/key/list",
        headers=_litellm_headers(),
    )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@router.get("/keys/{key}")
async def get_key_info(key: str, user: UserInfo = Depends(get_current_user)):
    """Get info for a specific API key via LiteLLM."""
    _ensure_http()
    resp = await deps.http_client.get(
        f"{deps.LITELLM_URL}/key/info",
        params={"key": key},
        headers=_litellm_headers(),
    )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@router.post("/keys/update")
async def update_key(request: KeyUpdateRequest, user: UserInfo = Depends(require_admin)):
    """Update an API key via LiteLLM."""
    _ensure_http()
    resp = await deps.http_client.post(
        f"{deps.LITELLM_URL}/key/update",
        json=request.model_dump(exclude_none=True),
        headers=_litellm_headers(),
    )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@router.post("/keys/delete")
async def delete_key(request: KeyDeleteRequest, user: UserInfo = Depends(require_admin)):
    """Delete API key(s) via LiteLLM."""
    _ensure_http()
    resp = await deps.http_client.post(
        f"{deps.LITELLM_URL}/key/delete",
        json=request.model_dump(),
        headers=_litellm_headers(),
    )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()
