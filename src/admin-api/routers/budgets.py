"""Budget management router — proxies to LiteLLM."""

import logging
from typing import Optional

import deps
from auth import UserInfo, get_current_user, require_admin
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)


class BudgetCreateRequest(BaseModel):
    max_budget: Optional[float] = None
    soft_budget: Optional[float] = None
    max_parallel_requests: Optional[int] = None
    tpm_limit: Optional[int] = None
    rpm_limit: Optional[int] = None


class BudgetUpdateRequest(BaseModel):
    budget_id: str
    max_budget: Optional[float] = None
    soft_budget: Optional[float] = None
    max_parallel_requests: Optional[int] = None
    tpm_limit: Optional[int] = None
    rpm_limit: Optional[int] = None


class BudgetDeleteRequest(BaseModel):
    id: str


def _litellm_headers() -> dict:
    return {"Authorization": f"Bearer {deps.LITELLM_MASTER_KEY}"}


def _ensure_http():
    if not deps.http_client:
        raise HTTPException(status_code=503, detail="HTTP client not available")


@router.get("/budgets")
async def list_budgets(user: UserInfo = Depends(get_current_user)):
    """List all budgets via LiteLLM."""
    _ensure_http()
    resp = await deps.http_client.get(
        f"{deps.LITELLM_URL}/budget/list",
        headers=_litellm_headers(),
    )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@router.post("/budgets")
async def create_budget(request: BudgetCreateRequest, user: UserInfo = Depends(require_admin)):
    """Create a new budget via LiteLLM."""
    _ensure_http()
    resp = await deps.http_client.post(
        f"{deps.LITELLM_URL}/budget/new",
        json=request.model_dump(exclude_none=True),
        headers=_litellm_headers(),
    )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@router.get("/budgets/{budget_id}")
async def get_budget(budget_id: str, user: UserInfo = Depends(get_current_user)):
    """Get a specific budget's info via LiteLLM."""
    _ensure_http()
    resp = await deps.http_client.get(
        f"{deps.LITELLM_URL}/budget/info",
        params={"budgets": budget_id},
        headers=_litellm_headers(),
    )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@router.post("/budgets/update")
async def update_budget(request: BudgetUpdateRequest, user: UserInfo = Depends(require_admin)):
    """Update a budget via LiteLLM."""
    _ensure_http()
    resp = await deps.http_client.post(
        f"{deps.LITELLM_URL}/budget/update",
        json=request.model_dump(exclude_none=True),
        headers=_litellm_headers(),
    )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@router.post("/budgets/delete")
async def delete_budget(request: BudgetDeleteRequest, user: UserInfo = Depends(require_admin)):
    """Delete a budget via LiteLLM."""
    _ensure_http()
    resp = await deps.http_client.post(
        f"{deps.LITELLM_URL}/budget/delete",
        json=request.model_dump(),
        headers=_litellm_headers(),
    )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()
