"""Playground Sessions router -- save and manage multi-model comparison sessions."""

import json
import logging
from typing import Dict, List, Optional

import deps
from auth import UserInfo, get_current_user, require_admin
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class PlaygroundSessionCreate(BaseModel):
    name: Optional[str] = None
    prompt: str
    models: List[str]
    settings: Optional[Dict] = None
    results: Optional[Dict] = None
    is_public: Optional[bool] = False


class PlaygroundSessionUpdate(BaseModel):
    name: Optional[str] = None
    prompt: Optional[str] = None
    models: Optional[List[str]] = None
    settings: Optional[Dict] = None
    results: Optional[Dict] = None
    is_public: Optional[bool] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_session(row) -> dict:
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "prompt": row["prompt"],
        "models": list(row["models"]) if row["models"] else [],
        "settings": json.loads(row["settings"]) if isinstance(row["settings"], str) else row["settings"],
        "results": json.loads(row["results"]) if isinstance(row["results"], str) else row["results"],
        "created_by": row["created_by"],
        "is_public": row["is_public"],
        "created_at": str(row["created_at"]) if row["created_at"] else None,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/playground/sessions")
async def list_sessions(
    created_by: Optional[str] = Query(default=None),
    is_public: Optional[bool] = Query(default=None),
    user: UserInfo = Depends(get_current_user),
):
    """List playground sessions, filterable by creator or public status."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        conditions = []
        values = []
        idx = 1

        if created_by:
            conditions.append(f"created_by = ${idx}")
            values.append(created_by)
            idx += 1

        if is_public is not None:
            conditions.append(f"is_public = ${idx}")
            values.append(is_public)
            idx += 1

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        query = f"""
            SELECT * FROM playground_sessions
            {where_clause}
            ORDER BY created_at DESC
        """
        rows = await conn.fetch(query, *values)
        return [_row_to_session(row) for row in rows]


@router.post("/playground/sessions")
async def create_session(
    data: PlaygroundSessionCreate,
    user: UserInfo = Depends(get_current_user),
):
    """Save a new playground session."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO playground_sessions (name, prompt, models, settings, results, created_by, is_public)
            VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6, $7)
            RETURNING *
            """,
            data.name,
            data.prompt,
            data.models,
            json.dumps(data.settings) if data.settings else None,
            json.dumps(data.results) if data.results else None,
            user.user_id,
            data.is_public or False,
        )
        logger.info("Playground session created by %s", user.user_id)
        return _row_to_session(row)


@router.get("/playground/sessions/{session_id}")
async def get_session(
    session_id: str,
    user: UserInfo = Depends(get_current_user),
):
    """Get a specific playground session."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM playground_sessions WHERE id = $1::uuid",
            session_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Session not found")
        return _row_to_session(row)


@router.put("/playground/sessions/{session_id}")
async def update_session(
    session_id: str,
    data: PlaygroundSessionUpdate,
    user: UserInfo = Depends(get_current_user),
):
    """Update a playground session. Requires admin or owner."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT * FROM playground_sessions WHERE id = $1::uuid",
            session_id,
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Session not found")

        # Check ownership or admin
        if existing["created_by"] != user.user_id and user.role != "admin":
            raise HTTPException(status_code=403, detail="Not authorized to update this session")

        updates = {}
        if data.name is not None:
            updates["name"] = data.name
        if data.prompt is not None:
            updates["prompt"] = data.prompt
        if data.models is not None:
            updates["models"] = data.models
        if data.settings is not None:
            updates["settings"] = json.dumps(data.settings)
        if data.results is not None:
            updates["results"] = json.dumps(data.results)
        if data.is_public is not None:
            updates["is_public"] = data.is_public

        if not updates:
            return _row_to_session(existing)

        set_clauses = []
        values = []
        for i, (key, value) in enumerate(updates.items(), start=1):
            if key in ("settings", "results"):
                set_clauses.append(f"{key} = ${i}::jsonb")
            else:
                set_clauses.append(f"{key} = ${i}")
            values.append(value)

        values.append(session_id)
        query = f"""
            UPDATE playground_sessions
            SET {', '.join(set_clauses)}
            WHERE id = ${len(values)}::uuid
            RETURNING *
        """
        row = await conn.fetchrow(query, *values)
        logger.info("Playground session updated: %s by %s", session_id, user.user_id)
        return _row_to_session(row)


@router.delete("/playground/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user: UserInfo = Depends(get_current_user),
):
    """Delete a playground session. Requires admin or owner."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT * FROM playground_sessions WHERE id = $1::uuid",
            session_id,
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Session not found")

        # Check ownership or admin
        if existing["created_by"] != user.user_id and user.role != "admin":
            raise HTTPException(status_code=403, detail="Not authorized to delete this session")

        await conn.execute(
            "DELETE FROM playground_sessions WHERE id = $1::uuid",
            session_id,
        )
        logger.info("Playground session deleted: %s by %s", session_id, user.user_id)
        return {"status": "ok"}
