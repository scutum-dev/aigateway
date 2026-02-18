"""FinOps reporting endpoints — queries LiteLLM_SpendLogs directly."""

import csv
import io
import json
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Optional

import deps
from auth import UserInfo, get_current_user
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()


class ReportPeriod(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class CostBreakdown(BaseModel):
    dimension: str
    value: str
    request_count: int
    input_tokens: int
    output_tokens: int
    total_cost: float


class CostReport(BaseModel):
    period: str
    start_date: date
    end_date: date
    total_cost: float
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    breakdown_by_model: list[CostBreakdown]
    breakdown_by_user: list[CostBreakdown]
    breakdown_by_team: list[CostBreakdown]
    generated_at: datetime


class TrendDataPoint(BaseModel):
    date: date
    cost: float
    requests: int
    tokens: int


class CostTrend(BaseModel):
    period: str
    data_points: list[TrendDataPoint]
    average_daily_cost: float
    trend_direction: str  # "increasing", "decreasing", "stable"
    percent_change: float


def get_date_range(period: ReportPeriod, start: Optional[date] = None, end: Optional[date] = None) -> tuple[date, date]:
    today = date.today()
    if period == ReportPeriod.DAILY:
        return today, today
    elif period == ReportPeriod.WEEKLY:
        return today - timedelta(days=today.weekday()), today
    elif period == ReportPeriod.MONTHLY:
        return today.replace(day=1), today
    elif period == ReportPeriod.CUSTOM:
        if not start or not end:
            raise ValueError("Custom period requires start and end dates")
        return start, end
    raise ValueError(f"Unknown period: {period}")


def _ensure_db():
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")


@router.get("/reports/cost", response_model=CostReport)
async def get_cost_report(
    user: UserInfo = Depends(get_current_user),
    period: ReportPeriod = Query(default=ReportPeriod.DAILY),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    user_id: Optional[str] = None,
    team_id: Optional[str] = None,
):
    _ensure_db()
    start, end = get_date_range(period, start_date, end_date)

    async with deps.db_pool.acquire() as conn:
        conditions = ['"startTime"::date >= $1', '"startTime"::date <= $2']
        params: list = [start, end]
        idx = 3

        if user_id:
            conditions.append(f'"user" = ${idx}')
            params.append(user_id)
            idx += 1
        if team_id:
            conditions.append(f"team_id = ${idx}")
            params.append(team_id)
            idx += 1

        where = " AND ".join(conditions)

        totals = await conn.fetchrow(
            f"""
            SELECT
                COUNT(*) as total_requests,
                COALESCE(SUM(prompt_tokens), 0) as total_input_tokens,
                COALESCE(SUM(completion_tokens), 0) as total_output_tokens,
                COALESCE(SUM(spend), 0) as total_cost
            FROM "LiteLLM_SpendLogs"
            WHERE {where}
            """,
            *params,
        )

        model_rows = await conn.fetch(
            f"""
            SELECT
                model,
                COUNT(*) as request_count,
                COALESCE(SUM(prompt_tokens), 0) as input_tokens,
                COALESCE(SUM(completion_tokens), 0) as output_tokens,
                COALESCE(SUM(spend), 0) as total_cost
            FROM "LiteLLM_SpendLogs"
            WHERE {where}
            GROUP BY model ORDER BY total_cost DESC
            """,
            *params,
        )

        user_rows = await conn.fetch(
            f"""
            SELECT
                COALESCE("user", 'unknown') as user_id,
                COUNT(*) as request_count,
                COALESCE(SUM(prompt_tokens), 0) as input_tokens,
                COALESCE(SUM(completion_tokens), 0) as output_tokens,
                COALESCE(SUM(spend), 0) as total_cost
            FROM "LiteLLM_SpendLogs"
            WHERE {where}
            GROUP BY "user" ORDER BY total_cost DESC LIMIT 20
            """,
            *params,
        )

        team_rows = await conn.fetch(
            f"""
            SELECT
                COALESCE(team_id, 'unknown') as team_id,
                COUNT(*) as request_count,
                COALESCE(SUM(prompt_tokens), 0) as input_tokens,
                COALESCE(SUM(completion_tokens), 0) as output_tokens,
                COALESCE(SUM(spend), 0) as total_cost
            FROM "LiteLLM_SpendLogs"
            WHERE {where}
            GROUP BY team_id ORDER BY total_cost DESC
            """,
            *params,
        )

        return CostReport(
            period=period.value,
            start_date=start,
            end_date=end,
            total_cost=float(totals["total_cost"]),
            total_requests=totals["total_requests"],
            total_input_tokens=totals["total_input_tokens"],
            total_output_tokens=totals["total_output_tokens"],
            breakdown_by_model=[
                CostBreakdown(
                    dimension="model",
                    value=r["model"],
                    request_count=r["request_count"],
                    input_tokens=r["input_tokens"],
                    output_tokens=r["output_tokens"],
                    total_cost=float(r["total_cost"]),
                )
                for r in model_rows
            ],
            breakdown_by_user=[
                CostBreakdown(
                    dimension="user",
                    value=r["user_id"],
                    request_count=r["request_count"],
                    input_tokens=r["input_tokens"],
                    output_tokens=r["output_tokens"],
                    total_cost=float(r["total_cost"]),
                )
                for r in user_rows
            ],
            breakdown_by_team=[
                CostBreakdown(
                    dimension="team",
                    value=r["team_id"],
                    request_count=r["request_count"],
                    input_tokens=r["input_tokens"],
                    output_tokens=r["output_tokens"],
                    total_cost=float(r["total_cost"]),
                )
                for r in team_rows
            ],
            generated_at=datetime.now(timezone.utc),
        )


@router.get("/reports/trend", response_model=CostTrend)
async def get_cost_trend(
    user: UserInfo = Depends(get_current_user),
    days: int = Query(default=30, ge=7, le=365),
    user_id: Optional[str] = None,
    team_id: Optional[str] = None,
    model: Optional[str] = None,
):
    _ensure_db()
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    async with deps.db_pool.acquire() as conn:
        conditions = ['"startTime"::date >= $1', '"startTime"::date <= $2']
        params: list = [start_date, end_date]
        idx = 3

        if user_id:
            conditions.append(f'"user" = ${idx}')
            params.append(user_id)
            idx += 1
        if team_id:
            conditions.append(f"team_id = ${idx}")
            params.append(team_id)
            idx += 1
        if model:
            conditions.append(f"model = ${idx}")
            params.append(model)
            idx += 1

        where = " AND ".join(conditions)

        rows = await conn.fetch(
            f"""
            SELECT
                "startTime"::date as date,
                COALESCE(SUM(spend), 0) as cost,
                COUNT(*) as requests,
                COALESCE(SUM(prompt_tokens + completion_tokens), 0) as tokens
            FROM "LiteLLM_SpendLogs"
            WHERE {where}
            GROUP BY "startTime"::date ORDER BY date
            """,
            *params,
        )

        data_points = [
            TrendDataPoint(date=r["date"], cost=float(r["cost"]), requests=r["requests"], tokens=r["tokens"])
            for r in rows
        ]

        if len(data_points) >= 2:
            costs = [dp.cost for dp in data_points]
            avg_cost = sum(costs) / len(costs)
            mid = len(costs) // 2
            first_half = sum(costs[:mid]) / mid if mid > 0 else 0
            second_half = sum(costs[mid:]) / (len(costs) - mid) if len(costs) - mid > 0 else 0
            percent_change = ((second_half - first_half) / first_half * 100) if first_half > 0 else 0
            if percent_change > 10:
                trend_direction = "increasing"
            elif percent_change < -10:
                trend_direction = "decreasing"
            else:
                trend_direction = "stable"
        else:
            avg_cost = data_points[0].cost if data_points else 0
            percent_change = 0
            trend_direction = "stable"

        return CostTrend(
            period=f"last_{days}_days",
            data_points=data_points,
            average_daily_cost=avg_cost,
            trend_direction=trend_direction,
            percent_change=percent_change,
        )


@router.get("/reports/export")
async def export_report(
    user: UserInfo = Depends(get_current_user),
    format: str = Query(default="csv", pattern="^(csv|json)$"),
    period: ReportPeriod = Query(default=ReportPeriod.MONTHLY),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    _ensure_db()
    start, end = get_date_range(period, start_date, end_date)

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                "startTime"::date as date,
                COALESCE("user", '') as user_id,
                COALESCE(team_id, '') as team_id,
                model,
                COUNT(*) as request_count,
                COALESCE(SUM(prompt_tokens), 0) as input_tokens,
                COALESCE(SUM(completion_tokens), 0) as output_tokens,
                COALESCE(SUM(spend), 0) as total_cost
            FROM "LiteLLM_SpendLogs"
            WHERE "startTime"::date >= $1 AND "startTime"::date <= $2
            GROUP BY "startTime"::date, "user", team_id, model
            ORDER BY date, model
            """,
            start,
            end,
        )

        if format == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(
                ["date", "user_id", "team_id", "model", "request_count", "input_tokens", "output_tokens", "total_cost"]
            )
            for row in rows:
                writer.writerow(
                    [
                        row["date"],
                        row["user_id"],
                        row["team_id"],
                        row["model"],
                        row["request_count"],
                        row["input_tokens"],
                        row["output_tokens"],
                        float(row["total_cost"]),
                    ]
                )
            output.seek(0)
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=cost_report_{start}_{end}.csv"},
            )
        else:
            data = [dict(row) for row in rows]
            for item in data:
                item["total_cost"] = float(item["total_cost"])
                item["date"] = str(item["date"])
            return StreamingResponse(
                iter([json.dumps(data, indent=2)]),
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename=cost_report_{start}_{end}.json"},
            )


@router.get("/reports/summary")
async def get_summary_stats(user: UserInfo = Depends(get_current_user)):
    _ensure_db()

    async with deps.db_pool.acquire() as conn:
        today_stats = await conn.fetchrow("""
            SELECT COALESCE(SUM(spend), 0) as cost,
                   COUNT(*) as requests,
                   COALESCE(SUM(prompt_tokens + completion_tokens), 0) as tokens
            FROM "LiteLLM_SpendLogs" WHERE "startTime"::date = CURRENT_DATE
        """)

        week_stats = await conn.fetchrow("""
            SELECT COALESCE(SUM(spend), 0) as cost, COUNT(*) as requests
            FROM "LiteLLM_SpendLogs" WHERE "startTime"::date >= DATE_TRUNC('week', CURRENT_DATE)
        """)

        month_stats = await conn.fetchrow("""
            SELECT COALESCE(SUM(spend), 0) as cost, COUNT(*) as requests
            FROM "LiteLLM_SpendLogs" WHERE "startTime"::date >= DATE_TRUNC('month', CURRENT_DATE)
        """)

        top_models = await conn.fetch("""
            SELECT model, COALESCE(SUM(spend), 0) as cost, COUNT(*) as cnt
            FROM "LiteLLM_SpendLogs"
            WHERE "startTime"::date >= DATE_TRUNC('month', CURRENT_DATE)
            GROUP BY model ORDER BY cost DESC LIMIT 5
        """)

        return {
            "today": {"cost": float(today_stats["cost"]), "requests": today_stats["requests"]},
            "this_week": {"cost": float(week_stats["cost"]), "requests": week_stats["requests"]},
            "this_month": {"cost": float(month_stats["cost"]), "requests": month_stats["requests"]},
            "top_models": [{"model": r["model"], "cost": float(r["cost"])} for r in top_models],
            "requests_today": today_stats["requests"],
            "tokens_today": today_stats["tokens"],
            "model_usage": {r["model"]: r["cnt"] for r in top_models},
        }
