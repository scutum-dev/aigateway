from typing import List

import deps
from auth import UserInfo, get_current_user, require_admin
from fastapi import APIRouter, Depends, HTTPException
from models import ModelConfig, ModelConfigUpdate

router = APIRouter()


@router.get("/models", response_model=List[ModelConfig])
async def list_models(user: UserInfo = Depends(get_current_user)):
    """List all model configurations."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM model_routing_config ORDER BY model_id")
        return [
            ModelConfig(
                model_id=row["model_id"],
                provider=row["provider"],
                tier=row["tier"],
                cost_per_1k_input=float(row["cost_per_1k_input"]),
                cost_per_1k_output=float(row["cost_per_1k_output"]),
                supports_streaming=row["supports_streaming"],
                supports_function_calling=row["supports_function_calling"],
                default_latency_sla_ms=row["default_latency_sla_ms"],
            )
            for row in rows
        ]


@router.put("/models/{model_id}", response_model=ModelConfig)
async def update_model(model_id: str, update: ModelConfigUpdate, user: UserInfo = Depends(require_admin)):
    """Update model configuration."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    updates = []
    params = []
    param_idx = 1

    for field, value in update.model_dump(exclude_unset=True).items():
        if value is not None:
            updates.append(f"{field} = ${param_idx}")
            params.append(value)
            param_idx += 1

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(model_id)

    async with deps.db_pool.acquire() as conn:
        query = f"UPDATE model_routing_config SET {', '.join(updates)} WHERE model_id = ${param_idx} RETURNING *"
        row = await conn.fetchrow(query, *params)

        if not row:
            raise HTTPException(status_code=404, detail="Model not found")

        return ModelConfig(**dict(row))
