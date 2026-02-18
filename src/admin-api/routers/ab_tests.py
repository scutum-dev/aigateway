"""A/B Tests router -- create, manage, and monitor A/B test experiments."""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import deps
from auth import UserInfo, get_current_user, require_admin
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ABTestCreate(BaseModel):
    name: str = Field(..., description="Human-readable test name")
    base_model: str = Field(..., description="Control model being tested against")
    variant_model: str = Field(..., description="Challenger model variant")
    traffic_split_percent: Optional[int] = Field(10, description="Percent of traffic to route to variant (0-100)")
    success_metric: Optional[str] = Field("cost_efficiency", description="Primary metric for evaluation")
    promotion_threshold: Optional[dict] = Field(None, description="Metric thresholds to auto-promote variant")
    rollback_threshold: Optional[dict] = Field(None, description="Metric thresholds to auto-rollback variant")
    auto_promote: Optional[bool] = Field(False, description="Auto-promote variant if it wins")
    auto_rollback: Optional[bool] = Field(True, description="Auto-rollback if variant degrades performance")


class ABTestUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Updated test name")
    base_model: Optional[str] = Field(None, description="Updated control model")
    variant_model: Optional[str] = Field(None, description="Updated variant model")
    traffic_split_percent: Optional[int] = Field(None, description="Percent of traffic to route to variant (0-100)")
    success_metric: Optional[str] = Field(None, description="Primary metric for evaluation")
    promotion_threshold: Optional[dict] = Field(None, description="Metric thresholds to auto-promote variant")
    rollback_threshold: Optional[dict] = Field(None, description="Metric thresholds to auto-rollback variant")
    auto_promote: Optional[bool] = Field(None, description="Auto-promote variant if it wins")
    auto_rollback: Optional[bool] = Field(None, description="Auto-rollback if variant degrades performance")


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
        "promotion_threshold": json.loads(row["promotion_threshold"])
        if isinstance(row["promotion_threshold"], str)
        else row["promotion_threshold"],
        "rollback_threshold": json.loads(row["rollback_threshold"])
        if isinstance(row["rollback_threshold"], str)
        else row["rollback_threshold"],
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
        "base_metrics": json.loads(row["base_metrics"])
        if isinstance(row["base_metrics"], str)
        else row["base_metrics"],
        "variant_metrics": json.loads(row["variant_metrics"])
        if isinstance(row["variant_metrics"], str)
        else row["variant_metrics"],
        "recommendation": row["recommendation"],
    }


async def _litellm_headers() -> dict:
    return {
        "Authorization": f"Bearer {deps.LITELLM_MASTER_KEY}",
        "Content-Type": "application/json",
    }


async def _add_variant_to_litellm(base_model: str, variant_model: str, traffic_split: int, test_id: str):
    """Add the variant model to LiteLLM with traffic weight."""
    if not deps.http_client:
        logger.warning("No HTTP client available, skipping LiteLLM integration")
        return None

    try:
        # Calculate weight: if split=10%, variant gets weight 0.1111 relative to base weight of 1.0
        # This means ~10% of traffic goes to variant
        variant_weight = round(traffic_split / max(100 - traffic_split, 1), 4)

        response = await deps.http_client.post(
            f"{deps.LITELLM_URL}/model/new",
            headers=await _litellm_headers(),
            json={
                "model_name": base_model,
                "litellm_params": {
                    "model": variant_model,
                    "weight": variant_weight,
                    "metadata": {"ab_test_id": test_id},
                },
                "model_info": {
                    "ab_test_id": test_id,
                    "ab_test_variant": True,
                },
            },
        )
        if response.status_code in (200, 201):
            result = response.json()
            logger.info("Added variant %s to LiteLLM for A/B test %s", variant_model, test_id)
            return result.get("model_info", {}).get("id") or result.get("model_id")
        else:
            logger.warning("LiteLLM /model/new returned %s: %s", response.status_code, response.text[:200])
            return None
    except Exception as e:
        logger.warning("Failed to add variant to LiteLLM: %s", e)
        return None


async def _remove_variant_from_litellm(test_id: str):
    """Remove A/B test variant model entries from LiteLLM."""
    if not deps.http_client:
        return

    try:
        # List all models and find the one tagged with this test
        response = await deps.http_client.get(
            f"{deps.LITELLM_URL}/v1/models",
            headers=await _litellm_headers(),
        )
        if response.status_code != 200:
            return

        models = response.json().get("data", [])
        for model in models:
            model_info = model.get("model_info", {}) or {}
            if model_info.get("ab_test_id") == test_id:
                model_id = model_info.get("id") or model.get("id")
                if model_id:
                    del_resp = await deps.http_client.post(
                        f"{deps.LITELLM_URL}/model/delete",
                        headers=await _litellm_headers(),
                        json={"id": model_id},
                    )
                    logger.info("Removed variant model %s from LiteLLM (status: %s)", model_id, del_resp.status_code)
    except Exception as e:
        logger.warning("Failed to remove variant from LiteLLM: %s", e)


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
        UPDATE ab_tests SET {", ".join(sets)}
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

        # Add variant model to LiteLLM for traffic splitting
        litellm_model_id = await _add_variant_to_litellm(
            row["base_model"], row["variant_model"], row["traffic_split_percent"], test_id
        )
        if litellm_model_id:
            logger.info("A/B test %s started with LiteLLM model %s", test_id, litellm_model_id)

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

        # Remove variant model from LiteLLM
        await _remove_variant_from_litellm(test_id)

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

        # Remove variant from LiteLLM — the variant becomes the new primary
        # (admin should update the main model config separately)
        await _remove_variant_from_litellm(test_id)
        logger.info("A/B test %s promoted: variant %s is now the recommended model", test_id, row["variant_model"])

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


# ---------------------------------------------------------------------------
# Metric Collection & Auto-Decisions
# ---------------------------------------------------------------------------


def _is_variant_better(base_metrics: dict, variant_metrics: dict, metric: str) -> str:
    """Compare base vs variant on the given metric. Returns 'promote', 'rollback', or 'continue'."""
    lower_is_better = {"avg_latency_ms", "p95_latency_ms", "avg_cost", "cost_efficiency", "error_rate"}

    base_val = base_metrics.get(metric)
    variant_val = variant_metrics.get(metric)

    if base_val is None or variant_val is None:
        return "continue"
    if base_val == 0 and variant_val == 0:
        return "continue"

    if metric in lower_is_better:
        improvement = (base_val - variant_val) / base_val if base_val > 0 else 0
    else:
        improvement = (variant_val - base_val) / base_val if base_val > 0 else 0

    if improvement > 0.05:
        return "promote"
    elif improvement < -0.10:
        return "rollback"
    return "continue"


async def _collect_model_metrics(conn, model: str, since) -> dict:
    """Query LiteLLM_SpendLogs for aggregated metrics for a model since a given time."""
    try:
        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) as request_count,
                COALESCE(AVG(EXTRACT(EPOCH FROM (end_time - starttime)) * 1000), 0) as avg_latency_ms,
                COALESCE(AVG(spend), 0) as avg_cost,
                COALESCE(SUM(spend), 0) as total_cost
            FROM "LiteLLM_SpendLogs"
            WHERE model = $1 AND starttime >= $2
            """,
            model,
            since,
        )
        if not row or row["request_count"] == 0:
            return {"request_count": 0}

        return {
            "request_count": row["request_count"],
            "avg_latency_ms": round(float(row["avg_latency_ms"]), 2),
            "avg_cost": round(float(row["avg_cost"]), 6),
            "total_cost": round(float(row["total_cost"]), 6),
        }
    except Exception as e:
        logger.warning("Failed to collect metrics for model %s: %s", model, e)
        return {"request_count": 0, "error": str(e)}


@router.post("/ab-tests/{test_id}/collect-metrics")
async def collect_metrics(test_id: str, user: UserInfo = Depends(require_admin)):
    """Collect metrics snapshot from LiteLLM spend logs for a running A/B test."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM ab_tests WHERE id = $1::uuid", test_id)
        if not row:
            raise HTTPException(status_code=404, detail="A/B test not found")
        if row["status"] != "running":
            raise HTTPException(status_code=400, detail="Test is not running")

        since = row["started_at"] or (datetime.now(timezone.utc) - timedelta(days=7))

        base_metrics = await _collect_model_metrics(conn, row["base_model"], since)
        variant_metrics = await _collect_model_metrics(conn, row["variant_model"], since)

        recommendation = _is_variant_better(base_metrics, variant_metrics, row["success_metric"])

        snapshot_row = await conn.fetchrow(
            """
            INSERT INTO ab_test_snapshots (test_id, base_metrics, variant_metrics, recommendation)
            VALUES ($1::uuid, $2::jsonb, $3::jsonb, $4)
            RETURNING *
            """,
            test_id,
            json.dumps(base_metrics),
            json.dumps(variant_metrics),
            recommendation,
        )

        # Auto-promote if enough samples and variant wins
        if row["auto_promote"] and recommendation == "promote" and variant_metrics.get("request_count", 0) > 500:
            await conn.execute(
                "UPDATE ab_tests SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE id = $1::uuid",
                test_id,
            )
            await _remove_variant_from_litellm(test_id)
            logger.info(
                "A/B test %s auto-promoted: variant %s wins on %s", test_id, row["variant_model"], row["success_metric"]
            )

        # Auto-rollback if variant degrades
        if row["auto_rollback"] and recommendation == "rollback" and variant_metrics.get("request_count", 0) > 200:
            await conn.execute(
                "UPDATE ab_tests SET status = 'rolled_back', completed_at = CURRENT_TIMESTAMP WHERE id = $1::uuid",
                test_id,
            )
            await _remove_variant_from_litellm(test_id)
            logger.info(
                "A/B test %s auto-rolled-back: variant %s degraded on %s",
                test_id,
                row["variant_model"],
                row["success_metric"],
            )

        return _row_to_snapshot(snapshot_row)


@router.get("/ab-tests/{test_id}/metrics")
async def get_ab_test_metrics(
    test_id: str, limit: int = Query(default=20, le=100), user: UserInfo = Depends(get_current_user)
):
    """Get metric snapshots for an A/B test (for charting)."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        test_row = await conn.fetchrow("SELECT * FROM ab_tests WHERE id = $1::uuid", test_id)
        if not test_row:
            raise HTTPException(status_code=404, detail="A/B test not found")

        rows = await conn.fetch(
            """
            SELECT * FROM ab_test_snapshots
            WHERE test_id = $1::uuid
            ORDER BY snapshot_at DESC
            LIMIT $2
            """,
            test_id,
            limit,
        )

        snapshots = [_row_to_snapshot(row) for row in reversed(rows)]

        return {
            "test": _row_to_test(test_row),
            "snapshots": snapshots,
            "snapshot_count": len(snapshots),
        }
