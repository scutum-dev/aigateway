"""Model management router — proxies to LiteLLM."""

import logging
from typing import Any, Dict, List, Optional

import deps
from auth import UserInfo, get_current_user, require_admin
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)


class ModelCreateRequest(BaseModel):
    model_name: str
    litellm_params: Dict[str, Any]
    model_info: Optional[Dict[str, Any]] = None


class ModelDeleteRequest(BaseModel):
    id: str


def _litellm_headers() -> dict:
    return {"Authorization": f"Bearer {deps.LITELLM_MASTER_KEY}"}


def _ensure_http():
    if not deps.http_client:
        raise HTTPException(status_code=503, detail="HTTP client not available")


@router.get("/models")
async def list_models(user: UserInfo = Depends(get_current_user)):
    """List all model configurations via LiteLLM."""
    _ensure_http()
    resp = await deps.http_client.get(
        f"{deps.LITELLM_URL}/model/info",
        headers=_litellm_headers(),
    )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@router.get("/models/{model_id}")
async def get_model(model_id: str, user: UserInfo = Depends(get_current_user)):
    """Get a specific model's info via LiteLLM."""
    _ensure_http()
    resp = await deps.http_client.get(
        f"{deps.LITELLM_URL}/model/info",
        headers=_litellm_headers(),
    )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    data = resp.json()
    # Filter to the specific model
    models = data.get("data", [])
    for m in models:
        info = m.get("model_info", {})
        if info.get("id") == model_id or m.get("model_name") == model_id:
            return m
    raise HTTPException(status_code=404, detail="Model not found")


@router.post("/models")
async def create_model(request: ModelCreateRequest, user: UserInfo = Depends(require_admin)):
    """Add a new model to LiteLLM."""
    _ensure_http()
    resp = await deps.http_client.post(
        f"{deps.LITELLM_URL}/model/new",
        json=request.model_dump(exclude_none=True),
        headers=_litellm_headers(),
    )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@router.post("/models/delete")
async def delete_model(request: ModelDeleteRequest, user: UserInfo = Depends(require_admin)):
    """Remove a model from LiteLLM."""
    _ensure_http()
    resp = await deps.http_client.post(
        f"{deps.LITELLM_URL}/model/delete",
        json=request.model_dump(),
        headers=_litellm_headers(),
    )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()
