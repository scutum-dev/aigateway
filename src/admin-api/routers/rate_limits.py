"""Granular rate limit policies router — CRUD, status, and event tracking."""

import json
from decimal import Decimal
from typing import Any, Dict, List, Optional

import deps
from auth import UserInfo, get_current_user, require_admin
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class RateLimitPolicyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    scope: str  # user, team, model, user_model, team_model
    scope_value: Optional[str] = None
    rpm_limit: Optional[int] = None
    tpm_limit: Optional[int] = None
    rpd_limit: Optional[int] = None
    tpd_limit: Optional[int] = None
    burst_multiplier: Optional[float] = 1.5
    burst_window_seconds: Optional[int] = 10
    priority: Optional[int] = 0


class RateLimitPolicyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    scope: Optional[str] = None
    scope_value: Optional[str] = None
    rpm_limit: Optional[int] = None
    tpm_limit: Optional[int] = None
    rpd_limit: Optional[int] = None
    tpd_limit: Optional[int] = None
    burst_multiplier: Optional[float] = None
    burst_window_seconds: Optional[int] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


class RateLimitPolicy(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    scope: str
    scope_value: Optional[str] = None
    rpm_limit: Optional[int] = None
    tpm_limit: Optional[int] = None
    rpd_limit: Optional[int] = None
    tpd_limit: Optional[int] = None
    burst_multiplier: float = 1.5
    burst_window_seconds: int = 10
    priority: int = 0
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class RateLimitEvent(BaseModel):
    id: str
    policy_id: Optional[str] = None
    scope: Optional[str] = None
    scope_value: Optional[str] = None
    limit_type: Optional[str] = None
    current_value: Optional[int] = None
    limit_value: Optional[int] = None
    action: Optional[str] = None
    created_at: Optional[str] = None


class RateLimitStatus(BaseModel):
    scope: str
    scope_value: Optional[str] = None
    current_rpm: int = 0
    rpm_limit: Optional[int] = None
    current_tpm: int = 0
    tpm_limit: Optional[int] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_policy(row) -> RateLimitPolicy:
    burst = row["burst_multiplier"]
    if isinstance(burst, Decimal):
        burst = float(burst)
    return RateLimitPolicy(
        id=str(row["id"]),
        name=row["name"],
        description=row["description"],
        scope=row["scope"],
        scope_value=row["scope_value"],
        rpm_limit=row["rpm_limit"],
        tpm_limit=row["tpm_limit"],
        rpd_limit=row["rpd_limit"],
        tpd_limit=row["tpd_limit"],
        burst_multiplier=burst if burst is not None else 1.5,
        burst_window_seconds=row["burst_window_seconds"] or 10,
        priority=row["priority"] or 0,
        is_active=row["is_active"],
        created_at=str(row["created_at"]) if row["created_at"] else None,
        updated_at=str(row["updated_at"]) if row["updated_at"] else None,
    )


def _row_to_event(row) -> RateLimitEvent:
    return RateLimitEvent(
        id=str(row["id"]),
        policy_id=str(row["policy_id"]) if row["policy_id"] else None,
        scope=row["scope"],
        scope_value=row["scope_value"],
        limit_type=row["limit_type"],
        current_value=row["current_value"],
        limit_value=row["limit_value"],
        action=row["action"],
        created_at=str(row["created_at"]) if row["created_at"] else None,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/rate-limits", response_model=List[RateLimitPolicy])
async def list_policies(user: UserInfo = Depends(get_current_user)):
    """List all rate limit policies."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM rate_limit_policies ORDER BY priority DESC, created_at DESC")
        return [_row_to_policy(row) for row in rows]


@router.post("/rate-limits", response_model=RateLimitPolicy)
async def create_policy(
    data: RateLimitPolicyCreate,
    user: UserInfo = Depends(require_admin),
):
    """Create a rate limit policy."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    valid_scopes = {"user", "team", "model", "user_model", "team_model", "global"}
    if data.scope not in valid_scopes:
        raise HTTPException(status_code=400, detail=f"Invalid scope. Must be one of: {', '.join(valid_scopes)}")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO rate_limit_policies (name, description, scope, scope_value, rpm_limit, tpm_limit, rpd_limit, tpd_limit, burst_multiplier, burst_window_seconds, priority)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING *
            """,
            data.name,
            data.description,
            data.scope,
            data.scope_value,
            data.rpm_limit,
            data.tpm_limit,
            data.rpd_limit,
            data.tpd_limit,
            data.burst_multiplier,
            data.burst_window_seconds,
            data.priority,
        )
        return _row_to_policy(row)


@router.get("/rate-limits/status")
async def rate_limit_status(user: UserInfo = Depends(get_current_user)):
    """Get current rate limit usage vs limits by querying Redis for current counts."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        policies = await conn.fetch("SELECT * FROM rate_limit_policies WHERE is_active = true ORDER BY priority DESC")

    statuses = []
    for policy in policies:
        current_rpm = 0
        current_tpm = 0

        # Try to read current counts from Redis
        if deps.redis_client:
            try:
                rpm_key = f"rl:{policy['scope']}:{policy['scope_value'] or 'global'}:rpm"
                tpm_key = f"rl:{policy['scope']}:{policy['scope_value'] or 'global'}:tpm"
                rpm_val = await deps.redis_client.get(rpm_key)
                tpm_val = await deps.redis_client.get(tpm_key)
                if rpm_val:
                    current_rpm = int(rpm_val)
                if tpm_val:
                    current_tpm = int(tpm_val)
            except Exception:
                pass

        statuses.append(
            RateLimitStatus(
                scope=policy["scope"],
                scope_value=policy["scope_value"],
                current_rpm=current_rpm,
                rpm_limit=policy["rpm_limit"],
                current_tpm=current_tpm,
                tpm_limit=policy["tpm_limit"],
            ).model_dump()
        )

    return statuses


@router.get("/rate-limits/{id}", response_model=RateLimitPolicy)
async def get_policy(id: str, user: UserInfo = Depends(get_current_user)):
    """Get a rate limit policy by ID."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM rate_limit_policies WHERE id = $1::uuid", id)
        if not row:
            raise HTTPException(status_code=404, detail="Rate limit policy not found")
        return _row_to_policy(row)


@router.put("/rate-limits/{id}", response_model=RateLimitPolicy)
async def update_policy(
    id: str,
    data: RateLimitPolicyUpdate,
    user: UserInfo = Depends(require_admin),
):
    """Update a rate limit policy."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    sets: list = []
    params: list = []
    idx = 1

    if data.name is not None:
        sets.append(f"name = ${idx}")
        params.append(data.name)
        idx += 1
    if data.description is not None:
        sets.append(f"description = ${idx}")
        params.append(data.description)
        idx += 1
    if data.scope is not None:
        sets.append(f"scope = ${idx}")
        params.append(data.scope)
        idx += 1
    if data.scope_value is not None:
        sets.append(f"scope_value = ${idx}")
        params.append(data.scope_value)
        idx += 1
    if data.rpm_limit is not None:
        sets.append(f"rpm_limit = ${idx}")
        params.append(data.rpm_limit)
        idx += 1
    if data.tpm_limit is not None:
        sets.append(f"tpm_limit = ${idx}")
        params.append(data.tpm_limit)
        idx += 1
    if data.rpd_limit is not None:
        sets.append(f"rpd_limit = ${idx}")
        params.append(data.rpd_limit)
        idx += 1
    if data.tpd_limit is not None:
        sets.append(f"tpd_limit = ${idx}")
        params.append(data.tpd_limit)
        idx += 1
    if data.burst_multiplier is not None:
        sets.append(f"burst_multiplier = ${idx}")
        params.append(data.burst_multiplier)
        idx += 1
    if data.burst_window_seconds is not None:
        sets.append(f"burst_window_seconds = ${idx}")
        params.append(data.burst_window_seconds)
        idx += 1
    if data.priority is not None:
        sets.append(f"priority = ${idx}")
        params.append(data.priority)
        idx += 1
    if data.is_active is not None:
        sets.append(f"is_active = ${idx}")
        params.append(data.is_active)
        idx += 1

    if not sets:
        raise HTTPException(status_code=400, detail="No fields to update")

    sets.append("updated_at = CURRENT_TIMESTAMP")
    params.append(id)

    query = f"""
        UPDATE rate_limit_policies SET {', '.join(sets)}
        WHERE id = ${idx}::uuid
        RETURNING *
    """

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(query, *params)
        if not row:
            raise HTTPException(status_code=404, detail="Rate limit policy not found")
        return _row_to_policy(row)


@router.delete("/rate-limits/{id}")
async def delete_policy(id: str, user: UserInfo = Depends(require_admin)):
    """Delete a rate limit policy."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        result = await conn.execute("DELETE FROM rate_limit_policies WHERE id = $1::uuid", id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Rate limit policy not found")
        return {"status": "ok"}


@router.get("/rate-limit-events", response_model=List[RateLimitEvent])
async def list_events(
    limit: int = Query(default=100, le=1000),
    user: UserInfo = Depends(get_current_user),
):
    """List recent rate limit events."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM rate_limit_events ORDER BY created_at DESC LIMIT $1",
            limit,
        )
        return [_row_to_event(row) for row in rows]
