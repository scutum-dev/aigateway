"""Chargeback / cost allocation router -- allocation rules, reports, and forecasts."""

import csv
import io
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import deps
from auth import UserInfo, get_current_user, require_admin
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class CostAllocationRuleCreate(BaseModel):
    name: str
    team_id: Optional[str] = None
    allocation_type: str
    allocation_target: str
    allocation_percent: Optional[float] = 100.0
    metadata: Optional[Dict[str, Any]] = None


class CostAllocationRule(BaseModel):
    id: str
    name: str
    team_id: Optional[str] = None
    allocation_type: str
    allocation_target: str
    allocation_percent: float
    metadata: Dict[str, Any]
    is_active: bool
    created_at: Optional[str] = None


class ChargebackReport(BaseModel):
    id: str
    report_period: str
    status: str
    total_cost: float
    breakdown: list
    generated_by: Optional[str] = None
    finalized_at: Optional[str] = None
    created_at: Optional[str] = None


class BudgetForecast(BaseModel):
    id: str
    team_id: Optional[str] = None
    forecast_period: str
    forecast_type: str
    forecasted_cost: Optional[float] = None
    confidence_low: Optional[float] = None
    confidence_high: Optional[float] = None
    actual_cost: Optional[float] = None
    created_at: Optional[str] = None


class GenerateReportRequest(BaseModel):
    period: str  # e.g. "2026-02"


class GenerateForecastRequest(BaseModel):
    team_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_rule(row) -> CostAllocationRule:
    meta = row["metadata"]
    if isinstance(meta, str):
        meta = json.loads(meta)
    return CostAllocationRule(
        id=str(row["id"]),
        name=row["name"],
        team_id=str(row["team_id"]) if row["team_id"] else None,
        allocation_type=row["allocation_type"],
        allocation_target=row["allocation_target"],
        allocation_percent=float(row["allocation_percent"]),
        metadata=meta if meta else {},
        is_active=row["is_active"],
        created_at=str(row["created_at"]) if row["created_at"] else None,
    )


def _row_to_report(row) -> ChargebackReport:
    breakdown = row["breakdown"]
    if isinstance(breakdown, str):
        breakdown = json.loads(breakdown)
    return ChargebackReport(
        id=str(row["id"]),
        report_period=row["report_period"],
        status=row["status"],
        total_cost=float(row["total_cost"]) if row["total_cost"] else 0,
        breakdown=breakdown if breakdown else [],
        generated_by=row["generated_by"],
        finalized_at=str(row["finalized_at"]) if row["finalized_at"] else None,
        created_at=str(row["created_at"]) if row["created_at"] else None,
    )


def _row_to_forecast(row) -> BudgetForecast:
    return BudgetForecast(
        id=str(row["id"]),
        team_id=str(row["team_id"]) if row["team_id"] else None,
        forecast_period=row["forecast_period"],
        forecast_type=row["forecast_type"],
        forecasted_cost=float(row["forecasted_cost"]) if row["forecasted_cost"] else None,
        confidence_low=float(row["confidence_low"]) if row["confidence_low"] else None,
        confidence_high=float(row["confidence_high"]) if row["confidence_high"] else None,
        actual_cost=float(row["actual_cost"]) if row["actual_cost"] else None,
        created_at=str(row["created_at"]) if row["created_at"] else None,
    )


# ---------------------------------------------------------------------------
# Cost Allocation Rules
# ---------------------------------------------------------------------------


@router.get("/cost-allocation/rules", response_model=List[CostAllocationRule])
async def list_rules(user: UserInfo = Depends(get_current_user)):
    """List all cost allocation rules."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM cost_allocation_rules ORDER BY created_at DESC")
        return [_row_to_rule(row) for row in rows]


@router.post("/cost-allocation/rules", response_model=CostAllocationRule)
async def create_rule(
    data: CostAllocationRuleCreate,
    user: UserInfo = Depends(require_admin),
):
    """Create a cost allocation rule."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO cost_allocation_rules (name, team_id, allocation_type, allocation_target, allocation_percent, metadata)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb)
            RETURNING *
            """,
            data.name,
            data.team_id,
            data.allocation_type,
            data.allocation_target,
            data.allocation_percent or 100.0,
            json.dumps(data.metadata or {}),
        )
        return _row_to_rule(row)


@router.put("/cost-allocation/rules/{id}", response_model=CostAllocationRule)
async def update_rule(
    id: str,
    data: CostAllocationRuleCreate,
    user: UserInfo = Depends(require_admin),
):
    """Update a cost allocation rule."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    sets: list = []
    params: list = []
    idx = 1

    if data.name is not None:
        sets.append(f"name = ${idx}")
        params.append(data.name)
        idx += 1
    if data.team_id is not None:
        sets.append(f"team_id = ${idx}")
        params.append(data.team_id)
        idx += 1
    if data.allocation_type is not None:
        sets.append(f"allocation_type = ${idx}")
        params.append(data.allocation_type)
        idx += 1
    if data.allocation_target is not None:
        sets.append(f"allocation_target = ${idx}")
        params.append(data.allocation_target)
        idx += 1
    if data.allocation_percent is not None:
        sets.append(f"allocation_percent = ${idx}")
        params.append(data.allocation_percent)
        idx += 1
    if data.metadata is not None:
        sets.append(f"metadata = ${idx}::jsonb")
        params.append(json.dumps(data.metadata))
        idx += 1

    if not sets:
        raise HTTPException(status_code=400, detail="No fields to update")

    params.append(id)
    query = f"""
        UPDATE cost_allocation_rules SET {', '.join(sets)}
        WHERE id = ${idx}::uuid
        RETURNING *
    """

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(query, *params)
        if not row:
            raise HTTPException(status_code=404, detail="Rule not found")
        return _row_to_rule(row)


@router.delete("/cost-allocation/rules/{id}")
async def delete_rule(id: str, user: UserInfo = Depends(require_admin)):
    """Delete a cost allocation rule."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        result = await conn.execute("DELETE FROM cost_allocation_rules WHERE id = $1::uuid", id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Rule not found")
        return {"status": "ok"}


# ---------------------------------------------------------------------------
# Chargeback Reports
# ---------------------------------------------------------------------------


@router.post("/chargeback/reports/generate", response_model=ChargebackReport)
async def generate_report(
    data: GenerateReportRequest,
    user: UserInfo = Depends(require_admin),
):
    """Generate a chargeback report for a given period (e.g. '2026-02')."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    period = data.period  # e.g. "2026-02"

    async with deps.db_pool.acquire() as conn:
        # Query LiteLLM_SpendLogs for the period, grouped by team_id
        spend_rows = await conn.fetch(
            """
            SELECT
                COALESCE(team_id, 'unassigned') AS team_id,
                COALESCE(SUM(spend), 0) AS total_spend,
                COUNT(*) AS request_count,
                COALESCE(SUM(total_tokens), 0) AS total_tokens
            FROM "LiteLLM_SpendLogs"
            WHERE to_char("startTime", 'YYYY-MM') = $1
            GROUP BY team_id
            ORDER BY total_spend DESC
            """,
            period,
        )

        # Get active allocation rules
        rules = await conn.fetch(
            "SELECT * FROM cost_allocation_rules WHERE is_active = true ORDER BY allocation_percent DESC"
        )

        # Build breakdown
        breakdown = []
        total_cost = Decimal("0")

        for sr in spend_rows:
            team_id = sr["team_id"]
            spend = Decimal(str(sr["total_spend"]))
            total_cost += spend

            # Check if there is an allocation rule for this team
            allocated = False
            for rule in rules:
                rule_team = str(rule["team_id"]) if rule["team_id"] else None
                if rule_team and rule_team == team_id:
                    pct = Decimal(str(rule["allocation_percent"])) / Decimal("100")
                    allocated_cost = spend * pct
                    breakdown.append({
                        "team_id": team_id,
                        "allocation_target": rule["allocation_target"],
                        "allocation_type": rule["allocation_type"],
                        "original_cost": float(spend),
                        "allocated_cost": float(allocated_cost),
                        "allocation_percent": float(rule["allocation_percent"]),
                        "request_count": sr["request_count"],
                        "total_tokens": sr["total_tokens"],
                    })
                    allocated = True

            if not allocated:
                breakdown.append({
                    "team_id": team_id,
                    "allocation_target": "direct",
                    "allocation_type": "direct",
                    "original_cost": float(spend),
                    "allocated_cost": float(spend),
                    "allocation_percent": 100.0,
                    "request_count": sr["request_count"],
                    "total_tokens": sr["total_tokens"],
                })

        # Store the report
        row = await conn.fetchrow(
            """
            INSERT INTO chargeback_reports (report_period, status, total_cost, breakdown, generated_by)
            VALUES ($1, 'draft', $2, $3::jsonb, $4)
            RETURNING *
            """,
            period,
            total_cost,
            json.dumps(breakdown),
            user.user_id,
        )
        return _row_to_report(row)


@router.get("/chargeback/reports", response_model=List[ChargebackReport])
async def list_reports(user: UserInfo = Depends(get_current_user)):
    """List all chargeback reports."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM chargeback_reports ORDER BY created_at DESC")
        return [_row_to_report(row) for row in rows]


@router.get("/chargeback/reports/{id}", response_model=ChargebackReport)
async def get_report(id: str, user: UserInfo = Depends(get_current_user)):
    """Get a specific chargeback report."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM chargeback_reports WHERE id = $1::uuid", id)
        if not row:
            raise HTTPException(status_code=404, detail="Report not found")
        return _row_to_report(row)


@router.get("/chargeback/reports/{id}/export")
async def export_report(
    id: str,
    format: str = Query(default="csv"),
    user: UserInfo = Depends(get_current_user),
):
    """Export a chargeback report as CSV or JSON."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM chargeback_reports WHERE id = $1::uuid", id)
        if not row:
            raise HTTPException(status_code=404, detail="Report not found")

        # Mark as exported
        await conn.execute(
            "UPDATE chargeback_reports SET exported_at = CURRENT_TIMESTAMP WHERE id = $1::uuid",
            id,
        )

        report = _row_to_report(row)

    if format == "json":
        return StreamingResponse(
            io.BytesIO(json.dumps({"report": report.model_dump()}, indent=2, default=str).encode()),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=chargeback_{report.report_period}.json"},
        )

    # CSV export
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["team_id", "allocation_target", "allocation_type", "original_cost", "allocated_cost", "allocation_percent", "request_count", "total_tokens"])
    for item in report.breakdown:
        writer.writerow([
            item.get("team_id", ""),
            item.get("allocation_target", ""),
            item.get("allocation_type", ""),
            item.get("original_cost", 0),
            item.get("allocated_cost", 0),
            item.get("allocation_percent", 0),
            item.get("request_count", 0),
            item.get("total_tokens", 0),
        ])

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=chargeback_{report.report_period}.csv"},
    )


@router.post("/chargeback/reports/{id}/finalize")
async def finalize_report(id: str, user: UserInfo = Depends(require_admin)):
    """Finalize a chargeback report (lock it from further edits)."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM chargeback_reports WHERE id = $1::uuid", id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Report not found")
        if row["status"] == "finalized":
            raise HTTPException(status_code=400, detail="Report already finalized")

        await conn.execute(
            """
            UPDATE chargeback_reports
            SET status = 'finalized', finalized_at = CURRENT_TIMESTAMP
            WHERE id = $1::uuid
            """,
            id,
        )
        return {"status": "finalized"}


# ---------------------------------------------------------------------------
# Budget Forecasts
# ---------------------------------------------------------------------------


@router.get("/reports/forecast", response_model=List[BudgetForecast])
async def list_forecasts(user: UserInfo = Depends(get_current_user)):
    """List budget forecasts."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM budget_forecasts ORDER BY created_at DESC")
        return [_row_to_forecast(row) for row in rows]


@router.post("/reports/forecast/generate", response_model=List[BudgetForecast])
async def generate_forecast(
    data: Optional[GenerateForecastRequest] = None,
    user: UserInfo = Depends(require_admin),
):
    """Generate a budget forecast using weighted moving average over last 3 months."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    team_filter = data.team_id if data else None

    async with deps.db_pool.acquire() as conn:
        # Get last 3 months of actual spend from LiteLLM_SpendLogs
        condition = ""
        params: list = []
        idx = 1

        if team_filter:
            condition = f"AND team_id = ${idx}"
            params.append(team_filter)
            idx += 1

        monthly_rows = await conn.fetch(
            f"""
            SELECT
                COALESCE(team_id, 'unassigned') AS team_id,
                to_char("startTime", 'YYYY-MM') AS month,
                COALESCE(SUM(spend), 0) AS total_spend
            FROM "LiteLLM_SpendLogs"
            WHERE "startTime" >= (CURRENT_DATE - INTERVAL '3 months')
            {condition}
            GROUP BY team_id, to_char("startTime", 'YYYY-MM')
            ORDER BY team_id, month
            """,
            *params,
        )

        # Group by team
        team_months: Dict[str, list] = {}
        for row in monthly_rows:
            tid = row["team_id"]
            if tid not in team_months:
                team_months[tid] = []
            team_months[tid].append(float(row["total_spend"]))

        # Calculate weighted moving average for next month
        # Weights: most recent month = 0.5, second = 0.3, third = 0.2
        weights = [0.2, 0.3, 0.5]
        now = datetime.now(timezone.utc)
        next_month = f"{now.year}-{now.month + 1:02d}" if now.month < 12 else f"{now.year + 1}-01"

        forecasts = []
        for tid, costs in team_months.items():
            # Pad with zeros if fewer than 3 months
            padded = [0.0] * (3 - len(costs)) + costs[-3:]
            weighted_avg = sum(c * w for c, w in zip(padded, weights))

            # Confidence bounds (+-20% / +-40%)
            confidence_low = weighted_avg * 0.6
            confidence_high = weighted_avg * 1.4

            row = await conn.fetchrow(
                """
                INSERT INTO budget_forecasts (team_id, forecast_period, forecast_type, forecasted_cost, confidence_low, confidence_high)
                VALUES ($1, $2, 'weighted_moving_avg', $3, $4, $5)
                RETURNING *
                """,
                tid if tid != "unassigned" else None,
                next_month,
                Decimal(str(round(weighted_avg, 10))),
                Decimal(str(round(confidence_low, 10))),
                Decimal(str(round(confidence_high, 10))),
            )
            forecasts.append(_row_to_forecast(row))

        return forecasts
