"""
FinOps Reporter Service

A FastAPI service that generates FinOps reports for AI Gateway usage.
Provides cost analytics, budget reports, and usage insights.

Features:
- Daily/weekly/monthly cost reports
- Per-user/team/model cost breakdown
- Budget utilization reports
- Cost trend analysis
- CSV/JSON export
"""

import os
import logging
from typing import Optional
from datetime import datetime, date, timedelta
from contextlib import asynccontextmanager
from decimal import Decimal
from enum import Enum

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
import asyncpg
import csv
import io
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ReportPeriod(str, Enum):
    """Report time periods."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class CostBreakdown(BaseModel):
    """Cost breakdown by dimension."""
    dimension: str
    value: str
    request_count: int
    input_tokens: int
    output_tokens: int
    total_cost: float


class CostReport(BaseModel):
    """Cost report model."""
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


class BudgetUtilization(BaseModel):
    """Budget utilization report."""
    user_id: Optional[str]
    team_id: Optional[str]
    budget_limit: float
    current_spend: float
    utilization_percent: float
    remaining: float
    projected_monthly: Optional[float]
    status: str  # "healthy", "warning", "critical"


class TrendDataPoint(BaseModel):
    """Single data point in trend analysis."""
    date: date
    cost: float
    requests: int
    tokens: int


class CostTrend(BaseModel):
    """Cost trend analysis."""
    period: str
    data_points: list[TrendDataPoint]
    average_daily_cost: float
    trend_direction: str  # "increasing", "decreasing", "stable"
    percent_change: float


# Global database pool
db_pool: Optional[asyncpg.Pool] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global db_pool

    # Setup OpenTelemetry
    otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    resource = Resource.create({"service.name": "finops-reporter"})
    provider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=otel_endpoint))
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    # Create database pool
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        try:
            db_pool = await asyncpg.create_pool(database_url, min_size=2, max_size=10)
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Could not connect to database: {e}")
            raise
    else:
        logger.warning("No DATABASE_URL configured")

    logger.info("FinOps reporter service started")
    yield

    # Cleanup
    if db_pool:
        await db_pool.close()
    logger.info("FinOps reporter service stopped")


app = FastAPI(
    title="FinOps Reporter Service",
    description="Generate cost reports and analytics for AI Gateway",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instrument with OpenTelemetry
FastAPIInstrumentor.instrument_app(app)

tracer = trace.get_tracer(__name__)


def get_date_range(period: ReportPeriod, start: Optional[date] = None, end: Optional[date] = None) -> tuple[date, date]:
    """Calculate date range for report period."""
    today = date.today()

    if period == ReportPeriod.DAILY:
        return today, today
    elif period == ReportPeriod.WEEKLY:
        start_of_week = today - timedelta(days=today.weekday())
        return start_of_week, today
    elif period == ReportPeriod.MONTHLY:
        start_of_month = today.replace(day=1)
        return start_of_month, today
    elif period == ReportPeriod.CUSTOM:
        if not start or not end:
            raise ValueError("Custom period requires start and end dates")
        return start, end
    else:
        raise ValueError(f"Unknown period: {period}")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "database": db_pool is not None}


@app.get("/reports/cost", response_model=CostReport)
async def get_cost_report(
    period: ReportPeriod = Query(default=ReportPeriod.DAILY),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    user_id: Optional[str] = None,
    team_id: Optional[str] = None,
):
    """
    Generate a cost report for the specified period.
    """
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    with tracer.start_as_current_span("generate_cost_report") as span:
        start, end = get_date_range(period, start_date, end_date)
        span.set_attribute("start_date", str(start))
        span.set_attribute("end_date", str(end))

        async with db_pool.acquire() as conn:
            # Build base query conditions
            conditions = ["date >= $1", "date <= $2"]
            params = [start, end]
            param_idx = 3

            if user_id:
                conditions.append(f"user_id = ${param_idx}")
                params.append(user_id)
                param_idx += 1

            if team_id:
                conditions.append(f"team_id = ${param_idx}")
                params.append(team_id)
                param_idx += 1

            where_clause = " AND ".join(conditions)

            # Get totals
            totals = await conn.fetchrow(f"""
                SELECT
                    COALESCE(SUM(request_count), 0) as total_requests,
                    COALESCE(SUM(input_tokens), 0) as total_input_tokens,
                    COALESCE(SUM(output_tokens), 0) as total_output_tokens,
                    COALESCE(SUM(total_cost), 0) as total_cost
                FROM cost_tracking_daily
                WHERE {where_clause}
            """, *params)

            # Breakdown by model
            model_breakdown = await conn.fetch(f"""
                SELECT
                    model,
                    SUM(request_count) as request_count,
                    SUM(input_tokens) as input_tokens,
                    SUM(output_tokens) as output_tokens,
                    SUM(total_cost) as total_cost
                FROM cost_tracking_daily
                WHERE {where_clause}
                GROUP BY model
                ORDER BY total_cost DESC
            """, *params)

            # Breakdown by user
            user_breakdown = await conn.fetch(f"""
                SELECT
                    COALESCE(user_id, 'unknown') as user_id,
                    SUM(request_count) as request_count,
                    SUM(input_tokens) as input_tokens,
                    SUM(output_tokens) as output_tokens,
                    SUM(total_cost) as total_cost
                FROM cost_tracking_daily
                WHERE {where_clause}
                GROUP BY user_id
                ORDER BY total_cost DESC
                LIMIT 20
            """, *params)

            # Breakdown by team
            team_breakdown = await conn.fetch(f"""
                SELECT
                    COALESCE(team_id, 'unknown') as team_id,
                    SUM(request_count) as request_count,
                    SUM(input_tokens) as input_tokens,
                    SUM(output_tokens) as output_tokens,
                    SUM(total_cost) as total_cost
                FROM cost_tracking_daily
                WHERE {where_clause}
                GROUP BY team_id
                ORDER BY total_cost DESC
            """, *params)

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
                        value=row["model"],
                        request_count=row["request_count"],
                        input_tokens=row["input_tokens"],
                        output_tokens=row["output_tokens"],
                        total_cost=float(row["total_cost"])
                    ) for row in model_breakdown
                ],
                breakdown_by_user=[
                    CostBreakdown(
                        dimension="user",
                        value=row["user_id"],
                        request_count=row["request_count"],
                        input_tokens=row["input_tokens"],
                        output_tokens=row["output_tokens"],
                        total_cost=float(row["total_cost"])
                    ) for row in user_breakdown
                ],
                breakdown_by_team=[
                    CostBreakdown(
                        dimension="team",
                        value=row["team_id"],
                        request_count=row["request_count"],
                        input_tokens=row["input_tokens"],
                        output_tokens=row["output_tokens"],
                        total_cost=float(row["total_cost"])
                    ) for row in team_breakdown
                ],
                generated_at=datetime.utcnow()
            )


@app.get("/reports/trend", response_model=CostTrend)
async def get_cost_trend(
    days: int = Query(default=30, ge=7, le=365),
    user_id: Optional[str] = None,
    team_id: Optional[str] = None,
    model: Optional[str] = None,
):
    """
    Get cost trend analysis over time.
    """
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    with tracer.start_as_current_span("get_cost_trend") as span:
        span.set_attribute("days", days)

        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        async with db_pool.acquire() as conn:
            conditions = ["date >= $1", "date <= $2"]
            params = [start_date, end_date]
            param_idx = 3

            if user_id:
                conditions.append(f"user_id = ${param_idx}")
                params.append(user_id)
                param_idx += 1

            if team_id:
                conditions.append(f"team_id = ${param_idx}")
                params.append(team_id)
                param_idx += 1

            if model:
                conditions.append(f"model = ${param_idx}")
                params.append(model)
                param_idx += 1

            where_clause = " AND ".join(conditions)

            rows = await conn.fetch(f"""
                SELECT
                    date,
                    SUM(total_cost) as cost,
                    SUM(request_count) as requests,
                    SUM(input_tokens + output_tokens) as tokens
                FROM cost_tracking_daily
                WHERE {where_clause}
                GROUP BY date
                ORDER BY date
            """, *params)

            data_points = [
                TrendDataPoint(
                    date=row["date"],
                    cost=float(row["cost"]),
                    requests=row["requests"],
                    tokens=row["tokens"]
                ) for row in rows
            ]

            # Calculate trend
            if len(data_points) >= 2:
                costs = [dp.cost for dp in data_points]
                avg_cost = sum(costs) / len(costs)

                # Compare first half to second half
                mid = len(costs) // 2
                first_half_avg = sum(costs[:mid]) / mid if mid > 0 else 0
                second_half_avg = sum(costs[mid:]) / (len(costs) - mid) if len(costs) - mid > 0 else 0

                if first_half_avg > 0:
                    percent_change = ((second_half_avg - first_half_avg) / first_half_avg) * 100
                else:
                    percent_change = 0

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
                percent_change=percent_change
            )


@app.get("/reports/budget-utilization")
async def get_budget_utilization(
    user_id: Optional[str] = None,
    team_id: Optional[str] = None,
):
    """
    Get budget utilization report.
    Integrates with LiteLLM to get budget limits.
    """
    # This would integrate with LiteLLM to get actual budget data
    # For now, return mock data structure
    return {
        "utilization": [],
        "message": "Budget data should be fetched from LiteLLM API"
    }


@app.get("/reports/export")
async def export_report(
    format: str = Query(default="csv", regex="^(csv|json)$"),
    period: ReportPeriod = Query(default=ReportPeriod.MONTHLY),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    """
    Export cost data in CSV or JSON format.
    """
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    start, end = get_date_range(period, start_date, end_date)

    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                date,
                user_id,
                team_id,
                model,
                request_count,
                input_tokens,
                output_tokens,
                total_cost
            FROM cost_tracking_daily
            WHERE date >= $1 AND date <= $2
            ORDER BY date, model
        """, start, end)

        if format == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                "date", "user_id", "team_id", "model",
                "request_count", "input_tokens", "output_tokens", "total_cost"
            ])
            for row in rows:
                writer.writerow([
                    row["date"],
                    row["user_id"],
                    row["team_id"],
                    row["model"],
                    row["request_count"],
                    row["input_tokens"],
                    row["output_tokens"],
                    float(row["total_cost"])
                ])

            output.seek(0)
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=cost_report_{start}_{end}.csv"}
            )
        else:
            data = [dict(row) for row in rows]
            # Convert Decimal to float for JSON serialization
            for item in data:
                item["total_cost"] = float(item["total_cost"])
                item["date"] = str(item["date"])

            return StreamingResponse(
                iter([json.dumps(data, indent=2)]),
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename=cost_report_{start}_{end}.json"}
            )


@app.get("/reports/summary")
async def get_summary_stats():
    """
    Get summary statistics for dashboard.
    """
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with db_pool.acquire() as conn:
        # Today's stats
        today_stats = await conn.fetchrow("""
            SELECT
                COALESCE(SUM(total_cost), 0) as cost,
                COALESCE(SUM(request_count), 0) as requests
            FROM cost_tracking_daily
            WHERE date = CURRENT_DATE
        """)

        # This week's stats
        week_stats = await conn.fetchrow("""
            SELECT
                COALESCE(SUM(total_cost), 0) as cost,
                COALESCE(SUM(request_count), 0) as requests
            FROM cost_tracking_daily
            WHERE date >= DATE_TRUNC('week', CURRENT_DATE)
        """)

        # This month's stats
        month_stats = await conn.fetchrow("""
            SELECT
                COALESCE(SUM(total_cost), 0) as cost,
                COALESCE(SUM(request_count), 0) as requests
            FROM cost_tracking_daily
            WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
        """)

        # Top models this month
        top_models = await conn.fetch("""
            SELECT model, SUM(total_cost) as cost
            FROM cost_tracking_daily
            WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
            GROUP BY model
            ORDER BY cost DESC
            LIMIT 5
        """)

        return {
            "today": {
                "cost": float(today_stats["cost"]),
                "requests": today_stats["requests"]
            },
            "this_week": {
                "cost": float(week_stats["cost"]),
                "requests": week_stats["requests"]
            },
            "this_month": {
                "cost": float(month_stats["cost"]),
                "requests": month_stats["requests"]
            },
            "top_models": [
                {"model": row["model"], "cost": float(row["cost"])}
                for row in top_models
            ]
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8082)
