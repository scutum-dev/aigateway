"""Granular rate limit policies router — CRUD, status, and event tracking."""

import json
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

import deps
from auth import UserInfo, get_current_user, require_admin
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class RateLimitPolicyCreate(BaseModel):
    name: str = Field(..., description="Human-readable policy name")
    description: Optional[str] = None
    scope: str  # user, team, model, user_model, team_model = Field(..., description="Scope: user, team, model, user_model, team_model, global")
    scope_value: Optional[str] = None
    rpm_limit: Optional[int] = Field(None, description="Requests per minute limit")
    tpm_limit: Optional[int] = Field(None, description="Tokens per minute limit")
    rpd_limit: Optional[int] = Field(None, description="Requests per day limit")
    tpd_limit: Optional[int] = Field(None, description="Tokens per day limit")
    burst_multiplier: Optional[float] = 1.5
    burst_window_seconds: Optional[int] = Field(10, description="Burst window duration in seconds")
    priority: Optional[int] = Field(0, description="Policy evaluation priority (lower = higher)")


class RateLimitPolicyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    scope: Optional[str] = None
    scope_value: Optional[str] = None
    rpm_limit: Optional[int] = None
    tpm_limit: Optional[int] = None
    rpd_limit: Optional[int] = Field(None, description="Requests per day limit")
    tpd_limit: Optional[int] = Field(None, description="Tokens per day limit")
    burst_multiplier: Optional[float] = Field(None, description="Multiplier for short burst allowance")
    burst_window_seconds: Optional[int] = Field(None, description="Burst window duration in seconds")
    priority: Optional[int] = Field(None, description="Policy evaluation priority (lower = higher)")
    is_active: Optional[bool] = Field(None, description="Whether this policy is enforced")


class RateLimitPolicy(BaseModel):
    id: str = Field(..., description="Unique policy identifier (UUID)")
    name: str = Field(..., description="Human-readable policy name")
    description: Optional[str] = None
    scope: str = Field(..., description="Scope: user, team, model, user_model, team_model, global")
    scope_value: Optional[str] = None
    rpm_limit: Optional[int] = None
    tpm_limit: Optional[int] = None
    rpd_limit: Optional[int] = None
    tpd_limit: Optional[int] = None
    burst_multiplier: float = 1.5
    burst_window_seconds: int = 10
    priority: int = 0
    is_active: bool = True
    created_at: Optional[str] = Field(None, description="ISO 8601 creation timestamp")
    updated_at: Optional[str] = Field(None, description="ISO 8601 last-update timestamp")


class RateLimitEvent(BaseModel):
    id: str = Field(..., description="Unique event identifier (UUID)")
    policy_id: Optional[str] = None
    scope: Optional[str] = None
    scope_value: Optional[str] = None
    limit_type: Optional[str] = None
    current_value: Optional[int] = None
    limit_value: Optional[int] = None
    action: Optional[str] = None
    created_at: Optional[str] = Field(None, description="ISO 8601 event timestamp")


class RateLimitStatus(BaseModel):
    scope: str = Field(..., description="Scope that was rate-limited")
    scope_value: Optional[str] = None
    current_rpm: int = 0
    rpm_limit: Optional[int] = None
    current_tpm: int = 0
    tpm_limit: Optional[int] = None
    current_rpd: int = 0
    rpd_limit: Optional[int] = None
    current_tpd: int = 0
    tpd_limit: Optional[int] = None
    burst_multiplier: float = 1.5


class RateLimitCheckRequest(BaseModel):
    user_id: Optional[str] = None
    team_id: Optional[str] = None
    model: Optional[str] = None


class RateLimitCheckResult(BaseModel):
    allowed: bool
    policies_checked: int = 0
    rejections: List[Dict[str, Any]] = Field(default_factory=list)
    closest_limits: List[Dict[str, Any]] = Field(default_factory=list)


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


async def _record_rate_limit_event(
    policy_id: str,
    scope: str,
    scope_value: Optional[str],
    limit_type: str,
    current_value: int,
    limit_value: int,
    action: str,
) -> None:
    """Record a rate limit event (rejected/burst_allowed/allowed) for auditing."""
    if not deps.db_pool:
        return
    try:
        async with deps.db_pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO rate_limit_events (policy_id, scope, scope_value, limit_type, current_value, limit_value, action)
                VALUES ($1::uuid, $2, $3, $4, $5, $6, $7)""",
                policy_id,
                scope,
                scope_value,
                limit_type,
                current_value,
                limit_value,
                action,
            )
    except Exception as e:
        logger.warning("Failed to record rate limit event: %s", e)


async def _sync_rate_limit_to_litellm(
    scope: str,
    scope_value: Optional[str],
    rpm_limit: Optional[int],
    tpm_limit: Optional[int],
    burst_multiplier: Optional[float] = None,
):
    """Sync rate limit policy to LiteLLM for team/user/team_model scopes."""
    if not deps.http_client or not scope_value:
        return

    headers = {
        "Authorization": f"Bearer {deps.LITELLM_MASTER_KEY}",
        "Content-Type": "application/json",
    }

    try:
        if scope == "team":
            update_data: Dict[str, Any] = {"team_id": scope_value}
            if rpm_limit is not None:
                update_data["rpm_limit"] = rpm_limit
            if tpm_limit is not None:
                update_data["tpm_limit"] = tpm_limit
            if burst_multiplier is not None and rpm_limit is not None:
                update_data["max_parallel_requests"] = int(
                    rpm_limit * burst_multiplier / 60
                )

            resp = await deps.http_client.post(
                f"{deps.LITELLM_URL}/team/update",
                headers=headers,
                json=update_data,
            )
            if resp.status_code == 200:
                logger.info(
                    "Synced rate limits to LiteLLM team %s: rpm=%s tpm=%s max_parallel=%s",
                    scope_value, rpm_limit, tpm_limit, update_data.get("max_parallel_requests"),
                )
            else:
                logger.warning("LiteLLM /team/update returned %s: %s", resp.status_code, resp.text[:200])

        elif scope == "user":
            update_data = {"key": scope_value}
            if rpm_limit is not None:
                update_data["rpm_limit"] = rpm_limit
            if tpm_limit is not None:
                update_data["tpm_limit"] = tpm_limit
            if burst_multiplier is not None and rpm_limit is not None:
                update_data["max_parallel_requests"] = int(
                    rpm_limit * burst_multiplier / 60
                )

            resp = await deps.http_client.post(
                f"{deps.LITELLM_URL}/key/update",
                headers=headers,
                json=update_data,
            )
            if resp.status_code == 200:
                logger.info(
                    "Synced rate limits to LiteLLM key %s: rpm=%s tpm=%s max_parallel=%s",
                    scope_value[:10], rpm_limit, tpm_limit, update_data.get("max_parallel_requests"),
                )
            else:
                logger.warning("LiteLLM /key/update returned %s: %s", resp.status_code, resp.text[:200])

        elif scope == "team_model":
            if ":" not in scope_value:
                logger.warning("team_model scope_value must be 'team_id:model_name', got: %s", scope_value)
                return

            team_id, model_name = scope_value.split(":", 1)
            metadata: Dict[str, Any] = {}
            if rpm_limit is not None:
                metadata["model_rpm_limit"] = {model_name: rpm_limit}
            if tpm_limit is not None:
                metadata["model_tpm_limit"] = {model_name: tpm_limit}
            if not metadata:
                return

            resp = await deps.http_client.post(
                f"{deps.LITELLM_URL}/team/update",
                headers=headers,
                json={"team_id": team_id, "metadata": metadata},
            )
            if resp.status_code == 200:
                logger.info(
                    "Synced model-scoped rate limits to LiteLLM team %s model %s: rpm=%s tpm=%s",
                    team_id, model_name, rpm_limit, tpm_limit,
                )
            else:
                logger.warning("LiteLLM /team/update (team_model) returned %s: %s", resp.status_code, resp.text[:200])

    except Exception as e:
        logger.warning("Failed to sync rate limit to LiteLLM: %s", e)


async def _clear_rate_limit_in_litellm(scope: str, scope_value: Optional[str]):
    """Remove rate limits from LiteLLM when a policy is deleted."""
    if not deps.http_client or not scope_value:
        return

    headers = {
        "Authorization": f"Bearer {deps.LITELLM_MASTER_KEY}",
        "Content-Type": "application/json",
    }

    try:
        if scope == "team":
            resp = await deps.http_client.post(
                f"{deps.LITELLM_URL}/team/update",
                headers=headers,
                json={"team_id": scope_value, "rpm_limit": None, "tpm_limit": None},
            )
            if resp.status_code == 200:
                logger.info("Cleared rate limits for LiteLLM team %s", scope_value)
        elif scope == "user":
            resp = await deps.http_client.post(
                f"{deps.LITELLM_URL}/key/update",
                headers=headers,
                json={"key": scope_value, "rpm_limit": None, "tpm_limit": None},
            )
            if resp.status_code == 200:
                logger.info("Cleared rate limits for LiteLLM key %s", scope_value[:10])
        elif scope == "team_model":
            if ":" in scope_value:
                team_id, model_name = scope_value.split(":", 1)
                resp = await deps.http_client.post(
                    f"{deps.LITELLM_URL}/team/update",
                    headers=headers,
                    json={
                        "team_id": team_id,
                        "metadata": {
                            "model_rpm_limit": {model_name: None},
                            "model_tpm_limit": {model_name: None},
                        },
                    },
                )
                if resp.status_code == 200:
                    logger.info("Cleared model-scoped rate limits for LiteLLM team %s model %s", team_id, model_name)
    except Exception as e:
        logger.warning("Failed to clear rate limit in LiteLLM: %s", e)


async def _get_redis_counter(key: str) -> int:
    """Read a single counter from Redis, returning 0 on any failure."""
    if not deps.redis_client:
        return 0
    try:
        val = await deps.redis_client.get(key)
        return int(val) if val else 0
    except Exception:
        return 0


async def _get_policy_counters(policy) -> Dict[str, int]:
    """Read all relevant counters for a policy from Redis."""
    prefix = f"rl:{policy['scope']}:{policy['scope_value'] or 'global'}"
    return {
        "rpm": await _get_redis_counter(f"{prefix}:rpm"),
        "tpm": await _get_redis_counter(f"{prefix}:tpm"),
        "rpd": await _get_redis_counter(f"{prefix}:rpd"),
        "tpd": await _get_redis_counter(f"{prefix}:tpd"),
    }


def _check_limit(
    current: int,
    base_limit: Optional[int],
    burst_multiplier: float,
    limit_type: str,
) -> Optional[Dict[str, Any]]:
    """Check a single limit dimension. Returns info dict if violated, else None."""
    if base_limit is None or base_limit <= 0:
        return None

    burst_limit = int(base_limit * burst_multiplier)
    usage_pct = round(current / base_limit * 100, 1) if base_limit else 0.0

    if current > burst_limit:
        return {
            "limit_type": limit_type,
            "current": current,
            "base_limit": base_limit,
            "burst_limit": burst_limit,
            "action": "rejected",
            "usage_pct": usage_pct,
        }
    elif current > base_limit:
        return {
            "limit_type": limit_type,
            "current": current,
            "base_limit": base_limit,
            "burst_limit": burst_limit,
            "action": "burst_allowed",
            "usage_pct": usage_pct,
        }
    return None


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

    await _sync_rate_limit_to_litellm(
        data.scope, data.scope_value, data.rpm_limit, data.tpm_limit, data.burst_multiplier
    )

    return _row_to_policy(row)


@router.get("/rate-limits/status")
async def rate_limit_status(user: UserInfo = Depends(get_current_user)):
    """Get current rate limit usage vs limits with event recording."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        policies = await conn.fetch("SELECT * FROM rate_limit_policies WHERE is_active = true ORDER BY priority DESC")

    statuses = []
    for policy in policies:
        counters = await _get_policy_counters(policy)

        burst = policy["burst_multiplier"]
        if isinstance(burst, Decimal):
            burst = float(burst)
        burst = burst if burst is not None else 1.5

        policy_id = str(policy["id"])
        scope = policy["scope"]
        scope_value = policy["scope_value"]

        for limit_type in ("rpm", "tpm", "rpd", "tpd"):
            base_limit = policy[f"{limit_type}_limit"]
            current = counters[limit_type]
            result = _check_limit(current, base_limit, burst, limit_type)
            if result is not None:
                await _record_rate_limit_event(
                    policy_id=policy_id,
                    scope=scope,
                    scope_value=scope_value,
                    limit_type=result["limit_type"],
                    current_value=result["current"],
                    limit_value=result["base_limit"],
                    action=result["action"],
                )

        statuses.append(
            RateLimitStatus(
                scope=scope,
                scope_value=scope_value,
                current_rpm=counters["rpm"],
                rpm_limit=policy["rpm_limit"],
                current_tpm=counters["tpm"],
                tpm_limit=policy["tpm_limit"],
                current_rpd=counters["rpd"],
                rpd_limit=policy["rpd_limit"],
                current_tpd=counters["tpd"],
                tpd_limit=policy["tpd_limit"],
                burst_multiplier=burst,
            ).model_dump()
        )

    return statuses


@router.post("/rate-limits/check", response_model=RateLimitCheckResult)
async def check_rate_limits(
    data: RateLimitCheckRequest,
    user: UserInfo = Depends(get_current_user),
):
    """Pre-flight check: evaluate all matching active policies for a hypothetical request."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    if not data.user_id and not data.team_id and not data.model:
        raise HTTPException(
            status_code=400,
            detail="At least one of user_id, team_id, or model must be provided",
        )

    scope_filters: List[tuple] = [("global", None)]
    if data.user_id:
        scope_filters.append(("user", data.user_id))
    if data.team_id:
        scope_filters.append(("team", data.team_id))
    if data.model:
        scope_filters.append(("model", data.model))
    if data.user_id and data.model:
        scope_filters.append(("user_model", f"{data.user_id}:{data.model}"))
    if data.team_id and data.model:
        scope_filters.append(("team_model", f"{data.team_id}:{data.model}"))

    conditions = []
    params: List[Any] = []
    idx = 1
    for scope, scope_value in scope_filters:
        if scope_value is None:
            conditions.append(f"(scope = ${idx} AND scope_value IS NULL)")
            params.append(scope)
            idx += 1
        else:
            conditions.append(f"(scope = ${idx} AND scope_value = ${idx + 1})")
            params.append(scope)
            params.append(scope_value)
            idx += 2

    where_clause = " OR ".join(conditions)
    query = f"""
        SELECT * FROM rate_limit_policies
        WHERE is_active = true AND ({where_clause})
        ORDER BY priority DESC
    """

    async with deps.db_pool.acquire() as conn:
        policies = await conn.fetch(query, *params)

    allowed = True
    rejections: List[Dict[str, Any]] = []
    closest_limits: List[Dict[str, Any]] = []

    for policy in policies:
        counters = await _get_policy_counters(policy)

        burst = policy["burst_multiplier"]
        if isinstance(burst, Decimal):
            burst = float(burst)
        burst = burst if burst is not None else 1.5

        policy_id = str(policy["id"])
        scope = policy["scope"]
        scope_value = policy["scope_value"]

        for limit_type in ("rpm", "tpm", "rpd", "tpd"):
            base_limit = policy[f"{limit_type}_limit"]
            current = counters[limit_type]

            if base_limit is None or base_limit <= 0:
                continue

            burst_limit = int(base_limit * burst)
            usage_pct = round(current / base_limit * 100, 1) if base_limit else 0.0

            limit_info = {
                "policy_id": policy_id,
                "policy_name": policy["name"],
                "scope": scope,
                "scope_value": scope_value,
                "limit_type": limit_type,
                "current": current,
                "base_limit": base_limit,
                "burst_limit": burst_limit,
                "usage_pct": usage_pct,
            }

            if current >= burst_limit:
                allowed = False
                limit_info["action"] = "rejected"
                rejections.append(limit_info)
                await _record_rate_limit_event(
                    policy_id=policy_id,
                    scope=scope,
                    scope_value=scope_value,
                    limit_type=limit_type,
                    current_value=current,
                    limit_value=base_limit,
                    action="rejected",
                )
            elif usage_pct >= 80.0:
                limit_info["action"] = "burst_allowed" if current > base_limit else "approaching"
                closest_limits.append(limit_info)

    closest_limits.sort(key=lambda x: x["usage_pct"], reverse=True)

    return RateLimitCheckResult(
        allowed=allowed,
        policies_checked=len(policies),
        rejections=rejections,
        closest_limits=closest_limits,
    )


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

    burst = row["burst_multiplier"]
    if isinstance(burst, Decimal):
        burst = float(burst)

    await _sync_rate_limit_to_litellm(
        row["scope"], row["scope_value"], row["rpm_limit"], row["tpm_limit"], burst
    )

    return _row_to_policy(row)


@router.delete("/rate-limits/{id}")
async def delete_policy(id: str, user: UserInfo = Depends(require_admin)):
    """Delete a rate limit policy."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        policy = await conn.fetchrow("SELECT scope, scope_value FROM rate_limit_policies WHERE id = $1::uuid", id)
        if not policy:
            raise HTTPException(status_code=404, detail="Rate limit policy not found")

        await conn.execute("DELETE FROM rate_limit_policies WHERE id = $1::uuid", id)

    await _clear_rate_limit_in_litellm(policy["scope"], policy["scope_value"])

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
