"""SLA monitoring router -- definitions, health metrics, violations, and failover rules."""

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import deps
from auth import UserInfo, get_current_user, require_admin
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class SLADefinitionCreate(BaseModel):
    name: str = Field(..., description="Human-readable SLA definition name")
    provider: Optional[str] = Field(None, description="Provider name (e.g. openai, anthropic)")
    model_pattern: Optional[str] = Field(None, description="Glob pattern for matching models")
    target_p50_ms: Optional[int] = Field(None, description="50th-percentile latency target in ms")
    target_p95_ms: Optional[int] = Field(None, description="95th-percentile latency target in ms")
    target_p99_ms: Optional[int] = Field(None, description="99th-percentile latency target in ms")
    target_error_rate: Optional[float] = Field(0.01, description="Max acceptable error rate (0.0-1.0)")
    target_availability: Optional[float] = Field(0.999, description="Min availability target (0.0-1.0)")
    evaluation_window_minutes: Optional[int] = Field(60, description="Rolling window size in minutes")
    alert_channels: Optional[List[str]] = Field(None, description="Notification channels for alerts")


class SLADefinition(BaseModel):
    id: str = Field(..., description="Unique SLA definition identifier (UUID)")
    name: str = Field(..., description="Human-readable SLA definition name")
    provider: Optional[str] = Field(None, description="Provider name (e.g. openai, anthropic)")
    model_pattern: Optional[str] = Field(None, description="Glob pattern for matching models")
    target_p50_ms: Optional[int] = Field(None, description="50th-percentile latency target in ms")
    target_p95_ms: Optional[int] = Field(None, description="95th-percentile latency target in ms")
    target_p99_ms: Optional[int] = Field(None, description="99th-percentile latency target in ms")
    target_error_rate: float = Field(..., description="Max acceptable error rate (0.0-1.0)")
    target_availability: float = Field(..., description="Min availability target (0.0-1.0)")
    evaluation_window_minutes: int = Field(..., description="Rolling window size in minutes")
    alert_channels: List[str] = Field(..., description="Notification channels for alerts")
    is_active: bool = Field(..., description="Whether this SLA definition is active")
    created_at: Optional[str] = Field(None, description="ISO 8601 creation timestamp")


class ProviderHealthMetric(BaseModel):
    id: str = Field(..., description="Unique health metric identifier (UUID)")
    provider: str = Field(..., description="Provider name (e.g. openai, anthropic)")
    model: str = Field(..., description="Model identifier")
    bucket_start: str = Field(..., description="Start of the time bucket (ISO 8601)")
    request_count: int = Field(..., description="Total requests in this bucket")
    error_count: int = Field(..., description="Failed requests in this bucket")
    p50_latency_ms: Optional[int] = Field(None, description="50th-percentile latency in ms")
    p95_latency_ms: Optional[int] = Field(None, description="95th-percentile latency in ms")
    p99_latency_ms: Optional[int] = Field(None, description="99th-percentile latency in ms")
    avg_latency_ms: Optional[int] = Field(None, description="Average latency in ms")
    total_tokens: int = Field(..., description="Total tokens consumed in this bucket")
    total_cost: float = Field(..., description="Total cost in USD for this bucket")


class SLAViolation(BaseModel):
    id: str = Field(..., description="Unique violation identifier (UUID)")
    sla_definition_id: Optional[str] = Field(None, description="Associated SLA definition ID")
    provider: Optional[str] = Field(None, description="Provider that violated the SLA")
    model: Optional[str] = Field(None, description="Model that violated the SLA")
    violation_type: Optional[str] = Field(None, description="Type: latency, error_rate, or availability")
    threshold_value: Optional[float] = Field(None, description="SLA threshold that was exceeded")
    actual_value: Optional[float] = Field(None, description="Observed value that breached the SLA")
    alert_sent: bool = Field(..., description="Whether an alert was dispatched")
    resolved_at: Optional[str] = Field(None, description="ISO 8601 resolution timestamp")
    created_at: Optional[str] = Field(None, description="ISO 8601 creation timestamp")


class FailoverRuleCreate(BaseModel):
    primary_model: str = Field(..., description="Model to monitor for failures")
    fallback_model: str = Field(..., description="Model to route to on failure")
    trigger_condition: Optional[str] = Field(None, description="Condition type: error_rate or latency")
    trigger_threshold: Optional[float] = Field(None, description="Threshold value to trigger failover")
    cooldown_minutes: Optional[int] = Field(15, description="Minutes to wait before re-triggering")


class FailoverRule(BaseModel):
    id: str = Field(..., description="Unique failover rule identifier (UUID)")
    primary_model: str = Field(..., description="Model being monitored for failures")
    fallback_model: str = Field(..., description="Model to route to on failure")
    trigger_condition: Optional[str] = Field(None, description="Condition type: error_rate or latency")
    trigger_threshold: Optional[float] = Field(None, description="Threshold value to trigger failover")
    cooldown_minutes: int = Field(..., description="Minutes to wait before re-triggering")
    is_active: bool = Field(..., description="Whether this failover rule is active")
    last_triggered_at: Optional[str] = Field(None, description="ISO 8601 timestamp of last trigger")
    created_at: Optional[str] = Field(None, description="ISO 8601 creation timestamp")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_definition(row) -> SLADefinition:
    return SLADefinition(
        id=str(row["id"]),
        name=row["name"],
        provider=row["provider"],
        model_pattern=row["model_pattern"],
        target_p50_ms=row["target_p50_ms"],
        target_p95_ms=row["target_p95_ms"],
        target_p99_ms=row["target_p99_ms"],
        target_error_rate=float(row["target_error_rate"]) if row["target_error_rate"] else 0.01,
        target_availability=float(row["target_availability"]) if row["target_availability"] else 0.999,
        evaluation_window_minutes=row["evaluation_window_minutes"] or 60,
        alert_channels=list(row["alert_channels"]) if row["alert_channels"] else [],
        is_active=row["is_active"],
        created_at=str(row["created_at"]) if row["created_at"] else None,
    )


def _row_to_metric(row) -> ProviderHealthMetric:
    return ProviderHealthMetric(
        id=str(row["id"]),
        provider=row["provider"],
        model=row["model"],
        bucket_start=str(row["bucket_start"]),
        request_count=row["request_count"] or 0,
        error_count=row["error_count"] or 0,
        p50_latency_ms=row["p50_latency_ms"],
        p95_latency_ms=row["p95_latency_ms"],
        p99_latency_ms=row["p99_latency_ms"],
        avg_latency_ms=row["avg_latency_ms"],
        total_tokens=row["total_tokens"] or 0,
        total_cost=float(row["total_cost"]) if row["total_cost"] else 0,
    )


def _row_to_violation(row) -> SLAViolation:
    return SLAViolation(
        id=str(row["id"]),
        sla_definition_id=str(row["sla_definition_id"]) if row["sla_definition_id"] else None,
        provider=row["provider"],
        model=row["model"],
        violation_type=row["violation_type"],
        threshold_value=float(row["threshold_value"]) if row["threshold_value"] else None,
        actual_value=float(row["actual_value"]) if row["actual_value"] else None,
        alert_sent=row["alert_sent"],
        resolved_at=str(row["resolved_at"]) if row["resolved_at"] else None,
        created_at=str(row["created_at"]) if row["created_at"] else None,
    )


def _row_to_failover(row) -> FailoverRule:
    return FailoverRule(
        id=str(row["id"]),
        primary_model=row["primary_model"],
        fallback_model=row["fallback_model"],
        trigger_condition=row["trigger_condition"],
        trigger_threshold=float(row["trigger_threshold"]) if row["trigger_threshold"] else None,
        cooldown_minutes=row["cooldown_minutes"] or 15,
        is_active=row["is_active"],
        last_triggered_at=str(row["last_triggered_at"]) if row["last_triggered_at"] else None,
        created_at=str(row["created_at"]) if row["created_at"] else None,
    )


# ---------------------------------------------------------------------------
# SLA Definitions
# ---------------------------------------------------------------------------


@router.get("/sla/definitions", response_model=List[SLADefinition])
async def list_definitions(user: UserInfo = Depends(get_current_user)):
    """List all SLA definitions."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM sla_definitions ORDER BY created_at DESC")
        return [_row_to_definition(row) for row in rows]


@router.post("/sla/definitions", response_model=SLADefinition)
async def create_definition(
    data: SLADefinitionCreate,
    user: UserInfo = Depends(require_admin),
):
    """Create an SLA definition."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO sla_definitions (name, provider, model_pattern, target_p50_ms, target_p95_ms, target_p99_ms,
                target_error_rate, target_availability, evaluation_window_minutes, alert_channels)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING *
            """,
            data.name,
            data.provider,
            data.model_pattern,
            data.target_p50_ms,
            data.target_p95_ms,
            data.target_p99_ms,
            data.target_error_rate or 0.01,
            data.target_availability or 0.999,
            data.evaluation_window_minutes or 60,
            data.alert_channels or [],
        )
        return _row_to_definition(row)


@router.put("/sla/definitions/{id}", response_model=SLADefinition)
async def update_definition(
    id: str,
    data: SLADefinitionCreate,
    user: UserInfo = Depends(require_admin),
):
    """Update an SLA definition."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    sets: list = []
    params: list = []
    idx = 1

    if data.name is not None:
        sets.append(f"name = ${idx}")
        params.append(data.name)
        idx += 1
    if data.provider is not None:
        sets.append(f"provider = ${idx}")
        params.append(data.provider)
        idx += 1
    if data.model_pattern is not None:
        sets.append(f"model_pattern = ${idx}")
        params.append(data.model_pattern)
        idx += 1
    if data.target_p50_ms is not None:
        sets.append(f"target_p50_ms = ${idx}")
        params.append(data.target_p50_ms)
        idx += 1
    if data.target_p95_ms is not None:
        sets.append(f"target_p95_ms = ${idx}")
        params.append(data.target_p95_ms)
        idx += 1
    if data.target_p99_ms is not None:
        sets.append(f"target_p99_ms = ${idx}")
        params.append(data.target_p99_ms)
        idx += 1
    if data.target_error_rate is not None:
        sets.append(f"target_error_rate = ${idx}")
        params.append(data.target_error_rate)
        idx += 1
    if data.target_availability is not None:
        sets.append(f"target_availability = ${idx}")
        params.append(data.target_availability)
        idx += 1
    if data.evaluation_window_minutes is not None:
        sets.append(f"evaluation_window_minutes = ${idx}")
        params.append(data.evaluation_window_minutes)
        idx += 1
    if data.alert_channels is not None:
        sets.append(f"alert_channels = ${idx}")
        params.append(data.alert_channels)
        idx += 1

    if not sets:
        raise HTTPException(status_code=400, detail="No fields to update")

    params.append(id)
    query = f"""
        UPDATE sla_definitions SET {', '.join(sets)}
        WHERE id = ${idx}::uuid
        RETURNING *
    """

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(query, *params)
        if not row:
            raise HTTPException(status_code=404, detail="SLA definition not found")
        return _row_to_definition(row)


@router.delete("/sla/definitions/{id}")
async def delete_definition(id: str, user: UserInfo = Depends(require_admin)):
    """Delete an SLA definition."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        result = await conn.execute("DELETE FROM sla_definitions WHERE id = $1::uuid", id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="SLA definition not found")
        return {"status": "ok"}


# ---------------------------------------------------------------------------
# Provider Health
# ---------------------------------------------------------------------------


@router.get("/sla/health", response_model=List[ProviderHealthMetric])
async def get_health(user: UserInfo = Depends(get_current_user)):
    """Get the latest provider health metrics (most recent bucket per provider/model)."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (provider, model) *
            FROM provider_health_metrics
            ORDER BY provider, model, bucket_start DESC
            """
        )
        return [_row_to_metric(row) for row in rows]


@router.get("/sla/health/history", response_model=List[ProviderHealthMetric])
async def get_health_history(
    provider: Optional[str] = Query(default=None),
    model: Optional[str] = Query(default=None),
    hours: Optional[int] = Query(default=24),
    user: UserInfo = Depends(get_current_user),
):
    """Get historical health metrics with optional filters."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    conditions = [f"bucket_start >= NOW() - INTERVAL '{hours} hours'"]
    params: list = []
    idx = 1

    if provider:
        conditions.append(f"provider = ${idx}")
        params.append(provider)
        idx += 1
    if model:
        conditions.append(f"model = ${idx}")
        params.append(model)
        idx += 1

    where = " AND ".join(conditions)
    query = f"SELECT * FROM provider_health_metrics WHERE {where} ORDER BY bucket_start DESC"

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        return [_row_to_metric(row) for row in rows]


# ---------------------------------------------------------------------------
# SLA Violations
# ---------------------------------------------------------------------------


@router.get("/sla/violations", response_model=List[SLAViolation])
async def list_violations(
    resolved: Optional[bool] = Query(default=None),
    user: UserInfo = Depends(get_current_user),
):
    """List SLA violations with optional filter."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    conditions: list = []
    params: list = []
    idx = 1

    if resolved is not None:
        if resolved:
            conditions.append("resolved_at IS NOT NULL")
        else:
            conditions.append("resolved_at IS NULL")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"SELECT * FROM sla_violations {where} ORDER BY created_at DESC"

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        return [_row_to_violation(row) for row in rows]


@router.get("/sla/violations/active", response_model=List[SLAViolation])
async def active_violations(user: UserInfo = Depends(get_current_user)):
    """Get unresolved violations."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM sla_violations WHERE resolved_at IS NULL ORDER BY created_at DESC"
        )
        return [_row_to_violation(row) for row in rows]


@router.post("/sla/violations/{id}/resolve")
async def resolve_violation(id: str, user: UserInfo = Depends(require_admin)):
    """Resolve (close) an SLA violation."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM sla_violations WHERE id = $1::uuid", id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Violation not found")
        if row["resolved_at"]:
            raise HTTPException(status_code=400, detail="Violation already resolved")

        await conn.execute(
            "UPDATE sla_violations SET resolved_at = CURRENT_TIMESTAMP WHERE id = $1::uuid",
            id,
        )
        return {"status": "resolved"}


# ---------------------------------------------------------------------------
# Failover Rules
# ---------------------------------------------------------------------------


@router.get("/sla/failover-rules", response_model=List[FailoverRule])
async def list_failover_rules(user: UserInfo = Depends(get_current_user)):
    """List all failover rules."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM provider_failover_rules ORDER BY created_at DESC")
        return [_row_to_failover(row) for row in rows]


@router.post("/sla/failover-rules", response_model=FailoverRule)
async def create_failover_rule(
    data: FailoverRuleCreate,
    user: UserInfo = Depends(require_admin),
):
    """Create a failover rule."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO provider_failover_rules (primary_model, fallback_model, trigger_condition, trigger_threshold, cooldown_minutes)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
            """,
            data.primary_model,
            data.fallback_model,
            data.trigger_condition,
            data.trigger_threshold,
            data.cooldown_minutes or 15,
        )
        return _row_to_failover(row)


@router.put("/sla/failover-rules/{id}", response_model=FailoverRule)
async def update_failover_rule(
    id: str,
    data: FailoverRuleCreate,
    user: UserInfo = Depends(require_admin),
):
    """Update a failover rule."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    sets: list = []
    params: list = []
    idx = 1

    if data.primary_model is not None:
        sets.append(f"primary_model = ${idx}")
        params.append(data.primary_model)
        idx += 1
    if data.fallback_model is not None:
        sets.append(f"fallback_model = ${idx}")
        params.append(data.fallback_model)
        idx += 1
    if data.trigger_condition is not None:
        sets.append(f"trigger_condition = ${idx}")
        params.append(data.trigger_condition)
        idx += 1
    if data.trigger_threshold is not None:
        sets.append(f"trigger_threshold = ${idx}")
        params.append(data.trigger_threshold)
        idx += 1
    if data.cooldown_minutes is not None:
        sets.append(f"cooldown_minutes = ${idx}")
        params.append(data.cooldown_minutes)
        idx += 1

    if not sets:
        raise HTTPException(status_code=400, detail="No fields to update")

    params.append(id)
    query = f"""
        UPDATE provider_failover_rules SET {', '.join(sets)}
        WHERE id = ${idx}::uuid
        RETURNING *
    """

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(query, *params)
        if not row:
            raise HTTPException(status_code=404, detail="Failover rule not found")
        return _row_to_failover(row)


@router.delete("/sla/failover-rules/{id}")
async def delete_failover_rule(id: str, user: UserInfo = Depends(require_admin)):
    """Delete a failover rule."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        result = await conn.execute("DELETE FROM provider_failover_rules WHERE id = $1::uuid", id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Failover rule not found")
        return {"status": "ok"}


@router.post("/sla/failover-rules/{id}/trigger")
async def trigger_failover(id: str, user: UserInfo = Depends(require_admin)):
    """Manually trigger a failover rule."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM provider_failover_rules WHERE id = $1::uuid", id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Failover rule not found")
        if not row["is_active"]:
            raise HTTPException(status_code=400, detail="Failover rule is inactive")

        await conn.execute(
            "UPDATE provider_failover_rules SET last_triggered_at = CURRENT_TIMESTAMP WHERE id = $1::uuid",
            id,
        )
        return {
            "status": "triggered",
            "primary_model": row["primary_model"],
            "fallback_model": row["fallback_model"],
        }


# ---------------------------------------------------------------------------
# SLA Compliance
# ---------------------------------------------------------------------------


@router.get("/sla/compliance")
async def get_compliance(user: UserInfo = Depends(get_current_user)):
    """Get monthly SLA compliance report (percentage of time within SLA targets)."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        # Get active SLA definitions
        definitions = await conn.fetch(
            "SELECT * FROM sla_definitions WHERE is_active = true"
        )

        # Get violations for current month
        violations = await conn.fetch(
            """
            SELECT sla_definition_id, COUNT(*) AS violation_count
            FROM sla_violations
            WHERE to_char(created_at, 'YYYY-MM') = to_char(CURRENT_TIMESTAMP, 'YYYY-MM')
            GROUP BY sla_definition_id
            """
        )

        violation_map: Dict[str, int] = {}
        for v in violations:
            if v["sla_definition_id"]:
                violation_map[str(v["sla_definition_id"])] = v["violation_count"]

        # Get total health metric buckets this month
        total_buckets = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM provider_health_metrics
            WHERE to_char(bucket_start, 'YYYY-MM') = to_char(CURRENT_TIMESTAMP, 'YYYY-MM')
            """
        ) or 0

        compliance = []
        for defn in definitions:
            defn_id = str(defn["id"])
            v_count = violation_map.get(defn_id, 0)

            # Compliance is % of buckets without violations
            if total_buckets > 0:
                compliance_pct = max(0, ((total_buckets - v_count) / total_buckets) * 100)
            else:
                compliance_pct = 100.0

            compliance.append({
                "sla_id": defn_id,
                "sla_name": defn["name"],
                "provider": defn["provider"],
                "model_pattern": defn["model_pattern"],
                "target_availability": float(defn["target_availability"]) if defn["target_availability"] else 0.999,
                "compliance_percent": round(compliance_pct, 2),
                "violations_this_month": v_count,
                "total_buckets": total_buckets,
                "status": "compliant" if compliance_pct >= float(defn["target_availability"] or 0.999) * 100 else "non_compliant",
            })

        return compliance
