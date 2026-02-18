"""A/B Tests router -- create, manage, and monitor A/B test experiments."""

import json
import logging
from typing import List, Optional

import deps
from auth import UserInfo, get_current_user, require_admin
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ABTestCreate(BaseModel):
    name: str
    base_model: str
    variant_model: str
    traffic_split_percent: Optional[int] = 10
    success_metric: Optional[str] = "cost_efficiency"
    promotion_threshold: Optional[dict] = None
    rollback_threshold: Optional[dict] = None
    auto_promote: Optional[bool] = False
    auto_rollback: Optional[bool] = True


class ABTestUpdate(BaseModel):
    name: Optional[str] = None
    base_model: Optional[str] = None
    variant_model: Optional[str] = None
    traffic_split_percent: Optional[int] = None
    success_metric: Optional[str] = None
    promotion_threshold: Optional[dict] = None
    rollback_threshold: Optional[dict] = None
    auto_promote: Optional[bool] = None
    auto_rollback: Optional[bool] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_test(row) -> dict:
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "status": row["status"],
        "base_model": row["base_model"],
        "variant_model": row["variant_model"],
        "traffic_split_percent": row["traffic_split_percent"],
        "success_metric": row["success_metric"],
        "promotion_threshold": json.loads(row["promotion_threshold"]) if isinstance(row["promotion_threshold"], str) else row["promotion_threshold"],
        "rollback_threshold": json.loads(row["rollback_threshold"]) if isinstance(row["rollback_threshold"], str) else row["rollback_threshold"],
        "auto_promote": row["auto_promote"],
        "auto_rollback": row["auto_rollback"],
        "started_at": str(row["started_at"]) if row["started_at"] else None,
        "completed_at": str(row["completed_at"]) if row["completed_at"] else None,
        "created_by": row["created_by"],
        "created_at": str(row["created_at"]) if row["created_at"] else None,
    }


def _row_to_snapshot(row) -> dict:
    return {
        "id": str(row["id"]),
        "test_id": str(row["test_id"]),
        "snapshot_at": str(row["snapshot_at"]) if row["snapshot_at"] else None,
        "base_metrics": json.loads(row["base_metrics"]) if isinstance(row["base_metrics"], str) else row["base_metrics"],
        "variant_metrics": json.loads(row["variant_metrics"]) if isinstance(row["variant_metrics"], str) else row["variant_metrics"],
        "recommendation": row["recommendation"],
    }


# ---------------------------------------------------------------------------
# CRUD Endpoints
# ---------------------------------------------------------------------------


@router.get("/ab-tests")
async def list_ab_tests(user: UserInfo = Depends(get_current_user)):
    """List all A/B tests."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM ab_tests ORDER BY created_at DESC")
        return [_row_to_test(row) for row in rows]


@router.post("/ab-tests")
async def create_ab_test(data: ABTestCreate, user: UserInfo = Depends(require_admin)):
    """Create a new A/B test."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO ab_tests (name, base_model, variant_model, traffic_split_percent,
                success_metric, promotion_threshold, rollback_threshold, auto_promote,
                auto_rollback, created_by)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8, $9, $10)
            RETURNING *
            """,
            data.name,
            data.base_model,
            data.variant_model,
            data.traffic_split_percent or 10,
            data.success_metric or "cost_efficiency",
            json.dumps(data.promotion_threshold) if data.promotion_threshold else None,
            json.dumps(data.rollback_threshold) if data.rollback_threshold else None,
            data.auto_promote if data.auto_promote is not None else False,
            data.auto_rollback if data.auto_rollback is not None else True,
            user.user_id,
        )
        return _row_to_test(row)


@router.get("/ab-tests/{test_id}")
async def get_ab_test(test_id: str, user: UserInfo = Depends(get_current_user)):
    """Get an A/B test with its latest snapshot."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM ab_tests WHERE id = $1::uuid", test_id)
        if not row:
            raise HTTPException(status_code=404, detail="A/B test not found")

        result = _row_to_test(row)

        # Get latest snapshot
        snapshot_row = await conn.fetchrow(
            """
            SELECT * FROM ab_test_snapshots
            WHERE test_id = $1::uuid
            ORDER BY snapshot_at DESC
            LIMIT 1
            """,
            test_id,
        )
        if snapshot_row:
            result["latest_snapshot"] = _row_to_snapshot(snapshot_row)
        else:
            result["latest_snapshot"] = None

        return result


@router.put("/ab-tests/{test_id}")
async def update_ab_test(
    test_id: str,
    data: ABTestUpdate,
    user: UserInfo = Depends(require_admin),
):
    """Update an A/B test."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    sets: list = []
    params: list = []
    idx = 1

    if data.name is not None:
        sets.append(f"name = ${idx}")
        params.append(data.name)
        idx += 1
    if data.base_model is not None:
        sets.append(f"base_model = ${idx}")
        params.append(data.base_model)
        idx += 1
    if data.variant_model is not None:
        sets.append(f"variant_model = ${idx}")
        params.append(data.variant_model)
        idx += 1
    if data.traffic_split_percent is not None:
        sets.append(f"traffic_split_percent = ${idx}")
        params.append(data.traffic_split_percent)
        idx += 1
    if data.success_metric is not None:
        sets.append(f"success_metric = ${idx}")
        params.append(data.success_metric)
        idx += 1
    if data.promotion_threshold is not None:
        sets.append(f"promotion_threshold = ${idx}::jsonb")
        params.append(json.dumps(data.promotion_threshold))
        idx += 1
    if data.rollback_threshold is not None:
        sets.append(f"rollback_threshold = ${idx}::jsonb")
        params.append(json.dumps(data.rollback_threshold))
        idx += 1
    if data.auto_promote is not None:
        sets.append(f"auto_promote = ${idx}")
        params.append(data.auto_promote)
        idx += 1
    if data.auto_rollback is not None:
        sets.append(f"auto_rollback = ${idx}")
        params.append(data.auto_rollback)
        idx += 1

    if not sets:
        raise HTTPException(status_code=400, detail="No fields to update")

    params.append(test_id)
    query = f"""
        UPDATE ab_tests SET {', '.join(sets)}
        WHERE id = ${idx}::uuid
        RETURNING *
    """

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(query, *params)
        if not row:
            raise HTTPException(status_code=404, detail="A/B test not found")
        return _row_to_test(row)


@router.delete("/ab-tests/{test_id}")
async def delete_ab_test(test_id: str, user: UserInfo = Depends(require_admin)):
    """Delete an A/B test."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        result = await conn.execute("DELETE FROM ab_tests WHERE id = $1::uuid", test_id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="A/B test not found")
        return {"status": "ok"}


# ---------------------------------------------------------------------------
# Lifecycle Endpoints
# ---------------------------------------------------------------------------


@router.post("/ab-tests/{test_id}/start")
async def start_ab_test(test_id: str, user: UserInfo = Depends(require_admin)):
    """Start an A/B test (set status to running)."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM ab_tests WHERE id = $1::uuid", test_id)
        if not row:
            raise HTTPException(status_code=404, detail="A/B test not found")
        if row["status"] not in ("draft", "completed", "rolled_back"):
            raise HTTPException(status_code=400, detail=f"Cannot start test in '{row['status']}' status")

        updated = await conn.fetchrow(
            """
            UPDATE ab_tests
            SET status = 'running', started_at = CURRENT_TIMESTAMP, completed_at = NULL
            WHERE id = $1::uuid
            RETURNING *
            """,
            test_id,
        )
        return _row_to_test(updated)


@router.post("/ab-tests/{test_id}/stop")
async def stop_ab_test(test_id: str, user: UserInfo = Depends(require_admin)):
    """Stop an A/B test (set status to completed)."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM ab_tests WHERE id = $1::uuid", test_id)
        if not row:
            raise HTTPException(status_code=404, detail="A/B test not found")
        if row["status"] != "running":
            raise HTTPException(status_code=400, detail="Test is not running")

        updated = await conn.fetchrow(
            """
            UPDATE ab_tests
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP
            WHERE id = $1::uuid
            RETURNING *
            """,
            test_id,
        )
        return _row_to_test(updated)


@router.post("/ab-tests/{test_id}/promote")
async def promote_ab_test(test_id: str, user: UserInfo = Depends(require_admin)):
    """Promote the variant model (set status to completed and record promotion)."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM ab_tests WHERE id = $1::uuid", test_id)
        if not row:
            raise HTTPException(status_code=404, detail="A/B test not found")
        if row["status"] != "running":
            raise HTTPException(status_code=400, detail="Test is not running")

        # Record a promotion snapshot
        await conn.execute(
            """
            INSERT INTO ab_test_snapshots (test_id, recommendation)
            VALUES ($1::uuid, 'promoted')
            """,
            test_id,
        )

        updated = await conn.fetchrow(
            """
            UPDATE ab_tests
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP
            WHERE id = $1::uuid
            RETURNING *
            """,
            test_id,
        )
        return _row_to_test(updated)


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------


@router.get("/ab-tests/{test_id}/snapshots")
async def list_ab_test_snapshots(test_id: str, user: UserInfo = Depends(get_current_user)):
    """Get all snapshots for an A/B test."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        # Verify test exists
        test_row = await conn.fetchrow("SELECT id FROM ab_tests WHERE id = $1::uuid", test_id)
        if not test_row:
            raise HTTPException(status_code=404, detail="A/B test not found")

        rows = await conn.fetch(
            """
            SELECT * FROM ab_test_snapshots
            WHERE test_id = $1::uuid
            ORDER BY snapshot_at DESC
            """,
            test_id,
        )
        return [_row_to_snapshot(row) for row in rows]
