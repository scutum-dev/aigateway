from fastapi import APIRouter, HTTPException, Depends
import httpx

import deps
from auth import get_current_user, require_admin, UserInfo
from models import KeyGenerateRequest, KeyUpdateRequest, KeyDeleteRequest

router = APIRouter()


@router.post("/keys/generate")
async def generate_key(
    request: KeyGenerateRequest,
    user: UserInfo = Depends(require_admin)
):
    """Generate a new API key via LiteLLM."""
    try:
        response = await deps.http_client.post(
            f"{deps.LITELLM_URL}/key/generate",
            json=request.model_dump(exclude_none=True),
            headers={"Authorization": f"Bearer {deps.LITELLM_MASTER_KEY}"},
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/keys")
async def list_keys(user: UserInfo = Depends(get_current_user)):
    """List all API keys via LiteLLM."""
    try:
        response = await deps.http_client.get(
            f"{deps.LITELLM_URL}/key/list",
            headers={"Authorization": f"Bearer {deps.LITELLM_MASTER_KEY}"},
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/keys/{key}")
async def get_key_info(
    key: str,
    user: UserInfo = Depends(get_current_user)
):
    """Get info about a specific API key via LiteLLM."""
    try:
        response = await deps.http_client.get(
            f"{deps.LITELLM_URL}/key/info",
            params={"key": key},
            headers={"Authorization": f"Bearer {deps.LITELLM_MASTER_KEY}"},
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/keys/update")
async def update_key(
    request: KeyUpdateRequest,
    user: UserInfo = Depends(require_admin)
):
    """Update an API key via LiteLLM."""
    try:
        response = await deps.http_client.post(
            f"{deps.LITELLM_URL}/key/update",
            json=request.model_dump(exclude_none=True),
            headers={"Authorization": f"Bearer {deps.LITELLM_MASTER_KEY}"},
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/keys/delete")
async def delete_keys(
    request: KeyDeleteRequest,
    user: UserInfo = Depends(require_admin)
):
    """Delete API keys via LiteLLM."""
    try:
        response = await deps.http_client.post(
            f"{deps.LITELLM_URL}/key/delete",
            json=request.model_dump(),
            headers={"Authorization": f"Bearer {deps.LITELLM_MASTER_KEY}"},
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
