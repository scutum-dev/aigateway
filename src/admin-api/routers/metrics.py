from datetime import datetime, timezone

import deps
from auth import UserInfo, get_current_user
from fastapi import APIRouter, Depends
from models import RealtimeMetrics

router = APIRouter()


@router.get("/metrics/realtime", response_model=RealtimeMetrics)
async def get_realtime_metrics(user: UserInfo = Depends(get_current_user)):
    """Get real-time platform metrics."""
    # Fetch from LiteLLM and database
    model_usage = {}
    provider_status = {}

    try:
        # Get LiteLLM health
        response = await deps.http_client.get(
            f"{deps.LITELLM_URL}/health/liveliness", headers={"Authorization": f"Bearer {deps.LITELLM_MASTER_KEY}"}
        )
        provider_status["litellm"] = response.status_code == 200
    except Exception:
        provider_status["litellm"] = False

    # Get today's stats from database
    total_cost_today = 0.0
    total_tokens_today = 0
    requests_today = 0

    if deps.db_pool:
        async with deps.db_pool.acquire() as conn:
            # Use LiteLLM's native spend logs table
            row = await conn.fetchrow("""
                SELECT
                    COALESCE(SUM(spend), 0) as total_cost,
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COUNT(*) as request_count
                FROM "LiteLLM_SpendLogs"
                WHERE "startTime"::date = CURRENT_DATE
            """)
            if row:
                total_cost_today = float(row["total_cost"])
                total_tokens_today = int(row["total_tokens"])
                requests_today = int(row["request_count"])

            # Get model usage from LiteLLM's native table
            rows = await conn.fetch("""
                SELECT model, COUNT(*) as count
                FROM "LiteLLM_SpendLogs"
                WHERE "startTime"::date = CURRENT_DATE
                GROUP BY model
            """)
            model_usage = {row["model"]: row["count"] for row in rows}

    return RealtimeMetrics(
        timestamp=datetime.now(timezone.utc),
        requests_per_minute=requests_today // max(1, datetime.now().hour * 60 + datetime.now().minute),
        active_users=0,  # Would need session tracking
        total_cost_today=total_cost_today,
        total_tokens_today=total_tokens_today,
        average_latency_ms=0,  # Would need Prometheus
        error_rate=0.0,  # Would need Prometheus
        model_usage=model_usage,
        provider_status=provider_status,
    )
