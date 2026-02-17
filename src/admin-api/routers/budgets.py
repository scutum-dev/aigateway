from typing import List

import deps
from auth import UserInfo, get_current_user, require_admin
from fastapi import APIRouter, Depends, HTTPException
from models import Budget, BudgetCreate, BudgetUpdate

router = APIRouter()


def _row_to_budget(row) -> Budget:
    """Convert database row to Budget model."""
    return Budget(
        id=str(row["id"]),
        name=row["name"],
        entity_type=row["entity_type"],
        entity_id=row["entity_id"],
        monthly_limit=float(row["monthly_limit"]),
        current_spend=float(row["current_spend"]),
        soft_limit_percent=float(row["soft_limit_percent"]),
        hard_limit_percent=float(row["hard_limit_percent"]),
        alert_email=row["alert_email"],
        is_active=row["is_active"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.get("/budgets", response_model=List[Budget])
async def list_budgets(user: UserInfo = Depends(get_current_user)):
    """List all budgets."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM budgets ORDER BY name")
        return [_row_to_budget(row) for row in rows]


@router.post("/budgets", response_model=Budget)
async def create_budget(budget: BudgetCreate, user: UserInfo = Depends(require_admin)):
    """Create a new budget."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO budgets (name, entity_type, entity_id, monthly_limit, soft_limit_percent, hard_limit_percent, alert_email)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
        """,
            budget.name,
            budget.entity_type,
            budget.entity_id,
            budget.monthly_limit,
            budget.soft_limit_percent,
            budget.hard_limit_percent,
            budget.alert_email,
        )

        return _row_to_budget(row)


@router.put("/budgets/{budget_id}", response_model=Budget)
async def update_budget(budget_id: str, update: BudgetUpdate, user: UserInfo = Depends(require_admin)):
    """Update a budget."""
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
    params.append(budget_id)

    async with deps.db_pool.acquire() as conn:
        query = f"UPDATE budgets SET {', '.join(updates)} WHERE id = ${param_idx} RETURNING *"
        row = await conn.fetchrow(query, *params)

        if not row:
            raise HTTPException(status_code=404, detail="Budget not found")

        return _row_to_budget(row)
