"""Routing Policies router -- manage model routing rules synced to LiteLLM."""

import json
import logging
from typing import List, Optional

import deps
from audit import log_audit_event
from auth import UserInfo, get_current_user, require_admin
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

POLICY_TYPES = ["fallback", "model_group", "routing_strategy", "conditional"]
ROUTING_STRATEGIES = [
    "usage-based-routing",
    "least-busy",
    "latency-based-routing",
    "cost-based-routing",
    "simple-shuffle",
]


class RoutingPolicyCreate(BaseModel):
    name: str = Field(..., description="Policy name")
    description: Optional[str] = Field(None, description="Policy description")
    policy_type: str = Field(
        ...,
        description="Type: fallback, model_group, routing_strategy, conditional",
    )
    config: dict = Field(
        ...,
        description=(
            "Policy configuration. "
            "fallback: {model: str, fallbacks: [str]}. "
            "model_group: {alias: str, models: [str]}. "
            "routing_strategy: {strategy: str, args: {}}. "
            "conditional: {condition: str, source_model: str, redirect_to: str}"
        ),
    )
    priority: int = Field(0, description="Evaluation order (higher = first)")
    is_active: bool = Field(True, description="Whether this policy is active")


class RoutingPolicy(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    policy_type: str
    config: dict
    priority: int = 0
    is_active: bool = True
    synced_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SyncResult(BaseModel):
    status: str
    synced: int = 0
    errors: list = []


class LiteLLMRouterStatus(BaseModel):
    routing_strategy: Optional[str] = None
    fallbacks: list = []
    model_group_aliases: dict = {}
    num_models: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_policy(row) -> RoutingPolicy:
    config = row["config"]
    if isinstance(config, str):
        config = json.loads(config)
    return RoutingPolicy(
        id=str(row["id"]),
        name=row["name"],
        description=row["description"],
        policy_type=row["policy_type"],
        config=config if isinstance(config, dict) else {},
        priority=row["priority"],
        is_active=row["is_active"],
        synced_at=str(row["synced_at"]) if row["synced_at"] else None,
        created_at=str(row["created_at"]) if row["created_at"] else None,
        updated_at=str(row["updated_at"]) if row["updated_at"] else None,
    )


async def _sync_fallbacks_to_litellm(conn) -> dict:
    """Sync all active fallback policies to LiteLLM router settings."""
    rows = await conn.fetch(
        "SELECT config FROM routing_policies WHERE policy_type = 'fallback' AND is_active = TRUE ORDER BY priority DESC"
    )
    fallbacks = []
    for row in rows:
        cfg = row["config"] if isinstance(row["config"], dict) else json.loads(row["config"])
        model = cfg.get("model", "")
        fb_list = cfg.get("fallbacks", [])
        if model and fb_list:
            fallbacks.append({model: fb_list})

    if not deps.http_client:
        return {"synced": False, "reason": "no_http_client"}

    try:
        resp = await deps.http_client.post(
            f"{deps.LITELLM_URL}/router/settings",
            headers={
                "Authorization": f"Bearer {deps.LITELLM_MASTER_KEY}",
                "Content-Type": "application/json",
            },
            json={"fallbacks": fallbacks},
            timeout=15.0,
        )
        if resp.status_code == 200:
            return {"synced": True, "count": len(fallbacks)}
        return {"synced": False, "status": resp.status_code, "detail": resp.text[:200]}
    except Exception as e:
        return {"synced": False, "error": str(e)}


async def _sync_model_groups_to_litellm(conn) -> dict:
    """Sync all active model_group policies to LiteLLM as model_group_alias."""
    rows = await conn.fetch(
        "SELECT config FROM routing_policies WHERE policy_type = 'model_group' AND is_active = TRUE ORDER BY priority DESC"
    )
    aliases = {}
    for row in rows:
        cfg = row["config"] if isinstance(row["config"], dict) else json.loads(row["config"])
        alias = cfg.get("alias", "")
        models = cfg.get("models", [])
        if alias and models:
            aliases[alias] = models

    if not deps.http_client:
        return {"synced": False, "reason": "no_http_client"}

    try:
        resp = await deps.http_client.post(
            f"{deps.LITELLM_URL}/router/settings",
            headers={
                "Authorization": f"Bearer {deps.LITELLM_MASTER_KEY}",
                "Content-Type": "application/json",
            },
            json={"model_group_alias": aliases},
            timeout=15.0,
        )
        if resp.status_code == 200:
            return {"synced": True, "count": len(aliases)}
        return {"synced": False, "status": resp.status_code, "detail": resp.text[:200]}
    except Exception as e:
        return {"synced": False, "error": str(e)}


async def _sync_routing_strategy_to_litellm(conn) -> dict:
    """Sync the active routing strategy to LiteLLM."""
    row = await conn.fetchrow(
        "SELECT config FROM routing_policies WHERE policy_type = 'routing_strategy' AND is_active = TRUE ORDER BY priority DESC LIMIT 1"
    )
    if not row:
        return {"synced": False, "reason": "no_active_strategy"}

    cfg = row["config"] if isinstance(row["config"], dict) else json.loads(row["config"])
    strategy = cfg.get("strategy", "usage-based-routing")
    args = cfg.get("args", {})

    if not deps.http_client:
        return {"synced": False, "reason": "no_http_client"}

    try:
        payload = {"routing_strategy": strategy, "routing_strategy_args": args}
        resp = await deps.http_client.post(
            f"{deps.LITELLM_URL}/router/settings",
            headers={
                "Authorization": f"Bearer {deps.LITELLM_MASTER_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15.0,
        )
        if resp.status_code == 200:
            return {"synced": True, "strategy": strategy}
        return {"synced": False, "status": resp.status_code, "detail": resp.text[:200]}
    except Exception as e:
        return {"synced": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/routing-policies", response_model=List[RoutingPolicy])
async def list_routing_policies(
    policy_type: Optional[str] = Query(None, description="Filter by policy type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    user: UserInfo = Depends(get_current_user),
):
    """List all routing policies."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    conditions = []
    params: list = []
    idx = 1

    if policy_type:
        conditions.append(f"policy_type = ${idx}")
        params.append(policy_type)
        idx += 1
    if is_active is not None:
        conditions.append(f"is_active = ${idx}")
        params.append(is_active)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT * FROM routing_policies {where} ORDER BY priority DESC, created_at DESC",
            *params,
        )
        return [_row_to_policy(row) for row in rows]


@router.post("/routing-policies", response_model=RoutingPolicy)
async def create_routing_policy(
    data: RoutingPolicyCreate,
    request: Request,
    user: UserInfo = Depends(require_admin),
):
    """Create a routing policy and sync to LiteLLM."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    if data.policy_type not in POLICY_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid policy_type. Must be one of: {POLICY_TYPES}",
        )

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO routing_policies (name, description, policy_type, config, priority, is_active)
            VALUES ($1, $2, $3, $4::jsonb, $5, $6)
            RETURNING *
            """,
            data.name,
            data.description,
            data.policy_type,
            json.dumps(data.config),
            data.priority,
            data.is_active,
        )
        policy = _row_to_policy(row)

        # Auto-sync to LiteLLM
        if data.is_active:
            sync_fn = {
                "fallback": _sync_fallbacks_to_litellm,
                "model_group": _sync_model_groups_to_litellm,
                "routing_strategy": _sync_routing_strategy_to_litellm,
            }.get(data.policy_type)
            if sync_fn:
                result = await sync_fn(conn)
                if result.get("synced"):
                    await conn.execute(
                        "UPDATE routing_policies SET synced_at = CURRENT_TIMESTAMP WHERE id = $1",
                        row["id"],
                    )
                    policy.synced_at = "just now"

        await log_audit_event(
            actor_id=user.user_id,
            action="create_routing_policy",
            resource_type="routing_policy",
            resource_id=policy.id,
            request=request,
        )
        return policy


@router.post("/routing-policies/sync", response_model=SyncResult)
async def sync_all_policies(
    request: Request,
    user: UserInfo = Depends(require_admin),
):
    """Sync all active routing policies to LiteLLM."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    synced = 0
    errors = []

    async with deps.db_pool.acquire() as conn:
        for policy_type, sync_fn in [
            ("fallback", _sync_fallbacks_to_litellm),
            ("model_group", _sync_model_groups_to_litellm),
            ("routing_strategy", _sync_routing_strategy_to_litellm),
        ]:
            result = await sync_fn(conn)
            if result.get("synced"):
                synced += 1
                await conn.execute(
                    "UPDATE routing_policies SET synced_at = CURRENT_TIMESTAMP WHERE policy_type = $1 AND is_active = TRUE",
                    policy_type,
                )
            elif result.get("error") or result.get("detail"):
                errors.append({"type": policy_type, **result})

    await log_audit_event(
        actor_id=user.user_id,
        action="sync_routing_policies",
        resource_type="routing_policy",
        request=request,
    )
    return SyncResult(
        status="ok" if not errors else "partial",
        synced=synced,
        errors=errors,
    )


@router.get("/routing-policies/litellm-status", response_model=LiteLLMRouterStatus)
async def get_litellm_router_status(
    user: UserInfo = Depends(get_current_user),
):
    """Get current LiteLLM router configuration."""
    if not deps.http_client:
        raise HTTPException(status_code=503, detail="HTTP client not available")

    try:
        resp = await deps.http_client.get(
            f"{deps.LITELLM_URL}/router/settings",
            headers={"Authorization": f"Bearer {deps.LITELLM_MASTER_KEY}"},
            timeout=10.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            return LiteLLMRouterStatus(
                routing_strategy=data.get("routing_strategy"),
                fallbacks=data.get("fallbacks", []),
                model_group_aliases=data.get("model_group_alias", {}),
                num_models=data.get("num_models", 0),
            )
        return LiteLLMRouterStatus()
    except Exception as e:
        logger.debug("Could not fetch LiteLLM router status: %s", e)
        return LiteLLMRouterStatus()


@router.get("/routing-policies/{policy_id}", response_model=RoutingPolicy)
async def get_routing_policy(
    policy_id: str,
    user: UserInfo = Depends(get_current_user),
):
    """Get a single routing policy."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM routing_policies WHERE id = $1::uuid", policy_id)
        if not row:
            raise HTTPException(status_code=404, detail="Routing policy not found")
        return _row_to_policy(row)


@router.put("/routing-policies/{policy_id}", response_model=RoutingPolicy)
async def update_routing_policy(
    policy_id: str,
    data: RoutingPolicyCreate,
    request: Request,
    user: UserInfo = Depends(require_admin),
):
    """Update a routing policy and re-sync to LiteLLM."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    if data.policy_type not in POLICY_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid policy_type. Must be one of: {POLICY_TYPES}",
        )

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE routing_policies
            SET name = $2, description = $3, policy_type = $4,
                config = $5::jsonb, priority = $6, is_active = $7,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $1::uuid
            RETURNING *
            """,
            policy_id,
            data.name,
            data.description,
            data.policy_type,
            json.dumps(data.config),
            data.priority,
            data.is_active,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Routing policy not found")

        policy = _row_to_policy(row)

        # Re-sync to LiteLLM
        sync_fn = {
            "fallback": _sync_fallbacks_to_litellm,
            "model_group": _sync_model_groups_to_litellm,
            "routing_strategy": _sync_routing_strategy_to_litellm,
        }.get(data.policy_type)
        if sync_fn:
            result = await sync_fn(conn)
            if result.get("synced"):
                await conn.execute(
                    "UPDATE routing_policies SET synced_at = CURRENT_TIMESTAMP WHERE id = $1",
                    row["id"],
                )

        await log_audit_event(
            actor_id=user.user_id,
            action="update_routing_policy",
            resource_type="routing_policy",
            resource_id=policy.id,
            request=request,
        )
        return policy


@router.delete("/routing-policies/{policy_id}")
async def delete_routing_policy(
    policy_id: str,
    request: Request,
    user: UserInfo = Depends(require_admin),
):
    """Delete a routing policy and re-sync to LiteLLM."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "DELETE FROM routing_policies WHERE id = $1::uuid RETURNING policy_type",
            policy_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Routing policy not found")

        # Re-sync the affected type
        sync_fn = {
            "fallback": _sync_fallbacks_to_litellm,
            "model_group": _sync_model_groups_to_litellm,
            "routing_strategy": _sync_routing_strategy_to_litellm,
        }.get(row["policy_type"])
        if sync_fn:
            await sync_fn(conn)

        await log_audit_event(
            actor_id=user.user_id,
            action="delete_routing_policy",
            resource_type="routing_policy",
            resource_id=policy_id,
            request=request,
        )
        return {"status": "deleted"}
