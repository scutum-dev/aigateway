"""Model Deprecations router -- track model deprecation and sunset schedules."""

import logging
from typing import Optional

import deps
from auth import UserInfo, get_current_user, require_admin
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ModelDeprecationCreate(BaseModel):
    model_name: str
    replacement_model: Optional[str] = None
    deprecation_date: Optional[str] = None
    sunset_date: Optional[str] = None
    message: Optional[str] = None


class ModelDeprecationUpdate(BaseModel):
    model_name: Optional[str] = None
    replacement_model: Optional[str] = None
    deprecation_date: Optional[str] = None
    sunset_date: Optional[str] = None
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_deprecation(row) -> dict:
    return {
        "id": str(row["id"]),
        "model_name": row["model_name"],
        "replacement_model": row["replacement_model"],
        "deprecation_date": str(row["deprecation_date"]) if row["deprecation_date"] else None,
        "sunset_date": str(row["sunset_date"]) if row["sunset_date"] else None,
        "message": row["message"],
        "created_at": str(row["created_at"]) if row["created_at"] else None,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/model-deprecations")
async def list_deprecations(user: UserInfo = Depends(get_current_user)):
    """List all model deprecations."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM model_deprecations ORDER BY created_at DESC"
        )
        return [_row_to_deprecation(row) for row in rows]


@router.post("/model-deprecations")
async def create_deprecation(
    data: ModelDeprecationCreate,
    user: UserInfo = Depends(require_admin),
):
    """Create a new model deprecation notice."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        # Check for duplicate model_name
        existing = await conn.fetchrow(
            "SELECT id FROM model_deprecations WHERE model_name = $1",
            data.model_name,
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Deprecation already exists for model: {data.model_name}",
            )

        row = await conn.fetchrow(
            """
            INSERT INTO model_deprecations (model_name, replacement_model, deprecation_date, sunset_date, message)
            VALUES ($1, $2, $3::date, $4::date, $5)
            RETURNING *
            """,
            data.model_name,
            data.replacement_model,
            data.deprecation_date,
            data.sunset_date,
            data.message,
        )
        logger.info("Model deprecation created for %s by %s", data.model_name, user.user_id)
        return _row_to_deprecation(row)


@router.get("/model-deprecations/check/{model_name:path}")
async def check_deprecation(
    model_name: str,
    user: UserInfo = Depends(get_current_user),
):
    """Check if a specific model is deprecated."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM model_deprecations WHERE model_name = $1",
            model_name,
        )
        if not row:
            return {"deprecated": False}
        return {
            "deprecated": True,
            "deprecation": _row_to_deprecation(row),
        }


@router.get("/model-deprecations/{deprecation_id}")
async def get_deprecation(
    deprecation_id: str,
    user: UserInfo = Depends(get_current_user),
):
    """Get a specific model deprecation."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM model_deprecations WHERE id = $1::uuid",
            deprecation_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Deprecation not found")
        return _row_to_deprecation(row)


@router.put("/model-deprecations/{deprecation_id}")
async def update_deprecation(
    deprecation_id: str,
    data: ModelDeprecationUpdate,
    user: UserInfo = Depends(require_admin),
):
    """Update a model deprecation."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT * FROM model_deprecations WHERE id = $1::uuid",
            deprecation_id,
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Deprecation not found")

        updates = {}
        if data.model_name is not None:
            updates["model_name"] = data.model_name
        if data.replacement_model is not None:
            updates["replacement_model"] = data.replacement_model
        if data.deprecation_date is not None:
            updates["deprecation_date"] = data.deprecation_date
        if data.sunset_date is not None:
            updates["sunset_date"] = data.sunset_date
        if data.message is not None:
            updates["message"] = data.message

        if not updates:
            return _row_to_deprecation(existing)

        set_clauses = []
        values = []
        for i, (key, value) in enumerate(updates.items(), start=1):
            if key in ("deprecation_date", "sunset_date"):
                set_clauses.append(f"{key} = ${i}::date")
            else:
                set_clauses.append(f"{key} = ${i}")
            values.append(value)

        values.append(deprecation_id)
        query = f"""
            UPDATE model_deprecations
            SET {', '.join(set_clauses)}
            WHERE id = ${len(values)}::uuid
            RETURNING *
        """
        row = await conn.fetchrow(query, *values)
        logger.info("Model deprecation updated: %s by %s", deprecation_id, user.user_id)
        return _row_to_deprecation(row)


@router.delete("/model-deprecations/{deprecation_id}")
async def delete_deprecation(
    deprecation_id: str,
    user: UserInfo = Depends(require_admin),
):
    """Delete a model deprecation."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM model_deprecations WHERE id = $1::uuid",
            deprecation_id,
        )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Deprecation not found")
        logger.info("Model deprecation deleted: %s by %s", deprecation_id, user.user_id)
        return {"status": "ok"}
