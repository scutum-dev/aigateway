"""Read-only diagnosis: gather context for an incident from the platform DB.

Pure asyncpg queries against tables already populated by SLA monitoring,
audit, event log, and budget alerts. Returns a structured assessment dict
the LLM uses as input to propose_remediation().
"""

from typing import Any, Dict, List, Optional


async def gather_diagnosis(
    db_pool,
    trigger_event: str,
    trigger_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a diagnosis dict for the LLM.

    Cheap to call: bounded queries (LIMIT, time-windowed). Returns even on
    partial failure so the LLM can still propose a notify-only action.
    """
    out: Dict[str, Any] = {
        "trigger_event": trigger_event,
        "trigger_payload": trigger_payload,
        "recent_violations": [],
        "provider_health": [],
        "recent_audit_for_resource": [],
        "related_events": [],
        "available_failover_rules": [],
        "active_rate_limit_policies": [],
        "active_guardrails": [],
        "affected_users": 0,
    }

    if not db_pool:
        return out

    provider = trigger_payload.get("provider")
    model = trigger_payload.get("model")
    team_id = trigger_payload.get("team_id")

    async with db_pool.acquire() as conn:
        out["recent_violations"] = await _recent_violations(conn, provider, model)
        out["provider_health"] = await _provider_health(conn, provider, model)
        out["recent_audit_for_resource"] = await _recent_audit(conn, provider, model, team_id)
        out["related_events"] = await _related_events(conn, trigger_event)
        out["available_failover_rules"] = await _failover_rules(conn, model)
        out["active_rate_limit_policies"] = await _rate_limit_policies(conn, team_id)
        out["active_guardrails"] = await _guardrails(conn)
        out["affected_users"] = await _affected_users(conn, team_id)

    return out


async def _recent_violations(conn, provider: Optional[str], model: Optional[str]) -> List[Dict]:
    rows = await conn.fetch(
        """
        SELECT id, provider, model, violation_type, threshold_value, actual_value, created_at
        FROM sla_violations
        WHERE created_at > NOW() - INTERVAL '15 minutes'
          AND ($1::text IS NULL OR provider = $1)
          AND ($2::text IS NULL OR model = $2)
          AND resolved_at IS NULL
        ORDER BY created_at DESC
        LIMIT 20
        """,
        provider,
        model,
    )
    return [
        {
            "id": str(r["id"]),
            "provider": r["provider"],
            "model": r["model"],
            "type": r["violation_type"],
            "threshold": float(r["threshold_value"]) if r["threshold_value"] is not None else None,
            "actual": float(r["actual_value"]) if r["actual_value"] is not None else None,
            "at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


async def _provider_health(conn, provider: Optional[str], model: Optional[str]) -> List[Dict]:
    rows = await conn.fetch(
        """
        SELECT provider, model, bucket_start, request_count, error_count,
               p50_latency_ms, p95_latency_ms, p99_latency_ms
        FROM provider_health_metrics
        WHERE bucket_start > NOW() - INTERVAL '1 hour'
          AND ($1::text IS NULL OR provider = $1)
          AND ($2::text IS NULL OR model = $2)
        ORDER BY bucket_start DESC
        LIMIT 12
        """,
        provider,
        model,
    )
    return [
        {
            "provider": r["provider"],
            "model": r["model"],
            "bucket": r["bucket_start"].isoformat() if r["bucket_start"] else None,
            "requests": r["request_count"],
            "errors": r["error_count"],
            "p50_ms": r["p50_latency_ms"],
            "p95_ms": r["p95_latency_ms"],
            "p99_ms": r["p99_latency_ms"],
        }
        for r in rows
    ]


async def _recent_audit(conn, provider: Optional[str], model: Optional[str], team_id: Optional[str]) -> List[Dict]:
    rows = await conn.fetch(
        """
        SELECT id, actor_id, action, resource_type, resource_id, resource_name, timestamp
        FROM audit_logs
        WHERE timestamp > NOW() - INTERVAL '1 hour'
          AND (
            ($1::text IS NOT NULL AND resource_name ILIKE '%' || $1 || '%')
            OR ($2::text IS NOT NULL AND resource_name ILIKE '%' || $2 || '%')
            OR ($3::text IS NOT NULL AND resource_id = $3)
          )
        ORDER BY timestamp DESC
        LIMIT 10
        """,
        provider,
        model,
        team_id,
    )
    return [
        {
            "id": str(r["id"]),
            "actor": r["actor_id"],
            "action": r["action"],
            "resource_type": r["resource_type"],
            "resource_id": r["resource_id"],
            "resource_name": r["resource_name"],
            "at": r["timestamp"].isoformat() if r["timestamp"] else None,
        }
        for r in rows
    ]


async def _related_events(conn, trigger_event: str) -> List[Dict]:
    rows = await conn.fetch(
        """
        SELECT id, event_type, payload, source_service, created_at
        FROM event_log
        WHERE created_at > NOW() - INTERVAL '15 minutes'
          AND event_type != $1
        ORDER BY created_at DESC
        LIMIT 10
        """,
        trigger_event,
    )
    return [
        {
            "id": str(r["id"]),
            "type": r["event_type"],
            "source": r["source_service"],
            "at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


async def _failover_rules(conn, model: Optional[str]) -> List[Dict]:
    rows = await conn.fetch(
        """
        SELECT id, primary_model, fallback_model, trigger_condition, is_active, last_triggered_at
        FROM provider_failover_rules
        WHERE is_active = true
          AND ($1::text IS NULL OR primary_model = $1 OR primary_model = '*')
        ORDER BY primary_model
        LIMIT 20
        """,
        model,
    )
    return [
        {
            "id": str(r["id"]),
            "primary_model": r["primary_model"],
            "fallback_model": r["fallback_model"],
            "condition": r["trigger_condition"],
            "last_triggered_at": r["last_triggered_at"].isoformat() if r["last_triggered_at"] else None,
        }
        for r in rows
    ]


async def _rate_limit_policies(conn, team_id: Optional[str]) -> List[Dict]:
    try:
        rows = await conn.fetch(
            """
            SELECT id, policy_name, scope_type, scope_id, rpm_limit, tpm_limit, is_active
            FROM rate_limit_policies
            WHERE is_active = true
              AND ($1::text IS NULL OR scope_id = $1 OR scope_id = '*')
            ORDER BY policy_name
            LIMIT 20
            """,
            team_id,
        )
    except Exception:
        return []
    return [
        {
            "id": str(r["id"]),
            "name": r["policy_name"],
            "scope_type": r["scope_type"],
            "scope_id": r["scope_id"],
            "rpm": r["rpm_limit"],
            "tpm": r["tpm_limit"],
        }
        for r in rows
    ]


async def _guardrails(conn) -> List[Dict]:
    try:
        rows = await conn.fetch(
            """
            SELECT id, name, mode, is_active
            FROM guardrails
            WHERE is_active = true
            ORDER BY name
            LIMIT 20
            """,
        )
    except Exception:
        return []
    return [{"id": str(r["id"]), "name": r["name"], "mode": r["mode"]} for r in rows]


async def _affected_users(conn, team_id: Optional[str]) -> int:
    if not team_id:
        return 0
    try:
        val = await conn.fetchval(
            "SELECT COUNT(DISTINCT actor_id) FROM audit_logs WHERE timestamp > NOW() - INTERVAL '1 hour' AND resource_id = $1",
            team_id,
        )
        return int(val or 0)
    except Exception:
        return 0
