import json

from fastapi import APIRouter, HTTPException, Depends

import deps
from auth import get_current_user, require_admin, UserInfo
from models import PlatformSettings

router = APIRouter()


@router.get("/settings", response_model=PlatformSettings)
async def get_settings(user: UserInfo = Depends(get_current_user)):
    """Get platform settings."""
    if not deps.db_pool:
        return PlatformSettings()

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT key, value FROM platform_settings")
        settings = PlatformSettings()

        for row in rows:
            key = row["key"]
            value = row["value"]
            if hasattr(settings, key):
                setattr(settings, key, value)

        return settings


@router.put("/settings", response_model=PlatformSettings)
async def update_settings(
    settings: PlatformSettings,
    user: UserInfo = Depends(require_admin)
):
    """Update platform settings."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        for key, value in settings.model_dump().items():
            await conn.execute("""
                INSERT INTO platform_settings (key, value, updated_at)
                VALUES ($1, $2, CURRENT_TIMESTAMP)
                ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = CURRENT_TIMESTAMP
            """, key, json.dumps(value))

    return settings
