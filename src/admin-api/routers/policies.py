from typing import List

from fastapi import APIRouter, HTTPException, Depends

import deps
from auth import get_current_user, require_admin, UserInfo
from models import RoutingPolicy, RoutingPolicyCreate

router = APIRouter()


@router.get("/routing-policies", response_model=List[RoutingPolicy])
async def list_routing_policies(user: UserInfo = Depends(get_current_user)):
    """List all routing policies."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM routing_policies ORDER BY priority DESC")
        return [
            RoutingPolicy(
                id=str(row["id"]),
                name=row["name"],
                description=row["description"],
                priority=row["priority"],
                condition=row["condition"],
                action=row["action"],
                target_models=row["target_models"],
                is_active=row["is_active"],
            )
            for row in rows
        ]


@router.post("/routing-policies", response_model=RoutingPolicy)
async def create_routing_policy(
    policy: RoutingPolicyCreate,
    user: UserInfo = Depends(require_admin)
):
    """Create a new routing policy."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO routing_policies (name, description, priority, condition, action, target_models)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *
        """, policy.name, policy.description, policy.priority, policy.condition, policy.action, policy.target_models)

        return RoutingPolicy(
            id=str(row["id"]),
            name=row["name"],
            description=row["description"],
            priority=row["priority"],
            condition=row["condition"],
            action=row["action"],
            target_models=row["target_models"],
            is_active=row["is_active"],
        )


@router.delete("/routing-policies/{policy_id}")
async def delete_routing_policy(
    policy_id: str,
    user: UserInfo = Depends(require_admin)
):
    """Delete a routing policy."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        result = await conn.execute("DELETE FROM routing_policies WHERE id = $1", policy_id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Policy not found")

    return {"status": "deleted"}
