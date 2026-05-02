"""SRE agent orchestration: incident lifecycle from trigger to closure.

The agent runs the diagnose → propose → notify phase synchronously when an
incident is opened, and persists status='awaiting_approval' so the UI can
surface it. The execute phase runs only after a human approves via the admin
UI; rejection closes the incident without mutating anything.
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

import actions
import asyncpg
import diagnose
import notifier
import risk
from admin_client import AdminClient
from llm import LLMProposer

logger = logging.getLogger(__name__)


async def open_incident(
    db_pool: asyncpg.Pool,
    trigger_event: str,
    trigger_payload: Dict[str, Any],
) -> str:
    """Create a new incident row and return its id."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO sre_incidents (id, trigger_event, trigger_payload, status)
            VALUES ($1::uuid, $2, $3::jsonb, 'open')
            RETURNING id
            """,
            str(uuid.uuid4()),
            trigger_event,
            json.dumps(trigger_payload),
        )
        return str(row["id"])


async def diagnose_and_propose(
    db_pool: asyncpg.Pool,
    http_client,
    proposer: LLMProposer,
    incident_id: str,
) -> None:
    """Run diagnose+propose, persist results, fire notifications, set status."""
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE sre_incidents SET status = 'diagnosing' WHERE id = $1::uuid",
            incident_id,
        )
        row = await conn.fetchrow(
            "SELECT trigger_event, trigger_payload FROM sre_incidents WHERE id = $1::uuid",
            incident_id,
        )
    if not row:
        logger.warning("Incident %s vanished before diagnosis", incident_id)
        return

    trigger_event = row["trigger_event"]
    trigger_payload = (
        json.loads(row["trigger_payload"])
        if isinstance(row["trigger_payload"], str)
        else (row["trigger_payload"] or {})
    )

    diagnosis = await diagnose.gather_diagnosis(db_pool, trigger_event, trigger_payload)
    proposed = await proposer.propose(diagnosis)

    plan: List[Dict[str, Any]] = []
    for step in proposed:
        action = step["action"]
        params = step["params"]
        spec = actions.ALLOWED_ACTIONS[action]
        if not spec.preconditions(diagnosis):
            logger.info("Skipping %s: preconditions not met", action)
            continue
        score, decision = risk.score(action, params, diagnosis)
        plan.append(
            {
                "action": action,
                "params": params,
                "risk_score": score,
                "decision": decision,
                "risk_class": spec.risk_class,
            }
        )

    next_status = "awaiting_approval" if plan else "closed_failed"
    summary = _summarize(trigger_event, trigger_payload, plan)

    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE sre_incidents
            SET diagnosis = $1::jsonb,
                proposed_plan = $2::jsonb,
                status = $3,
                outcome_summary = $4
            WHERE id = $5::uuid
            """,
            json.dumps(diagnosis, default=str),
            json.dumps(plan, default=str),
            next_status,
            summary,
            incident_id,
        )

        for step in plan:
            await conn.execute(
                """
                INSERT INTO sre_action_decisions (incident_id, action, params, risk_score, decision)
                VALUES ($1::uuid, $2, $3::jsonb, $4, $5)
                """,
                incident_id,
                step["action"],
                json.dumps(step["params"]),
                step["risk_score"],
                step["decision"],
            )

    severity = _severity_for(plan, trigger_event)
    await notifier.notify_all(
        db_pool,
        http_client,
        severity,
        summary,
        incident_id,
        extra={"plan_action_count": len(plan)},
    )


async def execute_approved(
    db_pool: asyncpg.Pool,
    admin_client: AdminClient,
    notify_http_client,
    incident_id: str,
    approver: str,
) -> Dict[str, Any]:
    """Execute every action on an incident's proposed_plan. Marks success/fail per step."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT proposed_plan, status FROM sre_incidents WHERE id = $1::uuid",
            incident_id,
        )
        if not row:
            return {"ok": False, "error": "Incident not found"}
        if row["status"] != "awaiting_approval":
            return {"ok": False, "error": f"Cannot execute incident in status {row['status']!r}"}

        plan = (
            json.loads(row["proposed_plan"]) if isinstance(row["proposed_plan"], str) else (row["proposed_plan"] or [])
        )
        await conn.execute(
            "UPDATE sre_incidents SET status = 'executing' WHERE id = $1::uuid",
            incident_id,
        )

    executed: List[Dict[str, Any]] = []
    overall_ok = True

    for step in plan:
        result = await _execute_step(admin_client, db_pool, notify_http_client, incident_id, step)
        executed.append(result)
        if not result.get("success"):
            overall_ok = False
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE sre_action_decisions
                SET approved_by = $1, executed_at = NOW(),
                    success = $2, error = $3
                WHERE incident_id = $4::uuid AND action = $5 AND executed_at IS NULL
                """,
                approver,
                result["success"],
                result.get("error"),
                incident_id,
                step["action"],
            )

    final_status = "closed_success" if overall_ok else "closed_failed"
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE sre_incidents
            SET executed_actions = $1::jsonb,
                status = $2,
                closed_at = NOW()
            WHERE id = $3::uuid
            """,
            json.dumps(executed, default=str),
            final_status,
            incident_id,
        )

    return {"ok": overall_ok, "executed": executed, "status": final_status}


async def reject_incident(
    db_pool: asyncpg.Pool,
    incident_id: str,
    approver: str,
    reason: Optional[str],
) -> Dict[str, Any]:
    async with db_pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE sre_incidents
            SET status = 'closed_rejected',
                outcome_summary = COALESCE(outcome_summary, '') || E'\nRejected by ' || $1 || ': ' || COALESCE($2, '(no reason)'),
                closed_at = NOW()
            WHERE id = $3::uuid AND status = 'awaiting_approval'
            """,
            approver,
            reason,
            incident_id,
        )
        if result.endswith(" 0"):
            return {"ok": False, "error": "Incident not found or not awaiting approval"}
    return {"ok": True, "status": "closed_rejected"}


async def _execute_step(
    admin_client: AdminClient,
    db_pool,
    http_client,
    incident_id: str,
    step: Dict[str, Any],
) -> Dict[str, Any]:
    name = step["action"]
    params = step["params"]
    spec = actions.ALLOWED_ACTIONS.get(name)
    if not spec:
        return {"action": name, "success": False, "error": f"Unknown action {name}"}

    built = spec.builder(params)
    kind = built.get("kind")

    if kind == "notify":
        delivered = await notifier.notify_all(
            db_pool,
            http_client,
            built["severity"],
            built["summary"],
            incident_id,
        )
        return {"action": name, "success": True, "delivered": delivered}

    if kind == "admin_api":
        result = await admin_client.call(built["method"], built["path"], built.get("body"))
        return {
            "action": name,
            "success": result["ok"],
            "status": result.get("status"),
            "response": result.get("body"),
            "error": result.get("error"),
        }

    return {"action": name, "success": False, "error": f"Unhandled action kind: {kind}"}


def _summarize(
    trigger_event: str,
    trigger_payload: Dict[str, Any],
    plan: List[Dict[str, Any]],
) -> str:
    target = (
        trigger_payload.get("model") or trigger_payload.get("provider") or trigger_payload.get("team_id") or "platform"
    )
    if not plan:
        return f"{trigger_event} on {target}: no remediation proposed (manual review required)."
    actions_summary = ", ".join(s["action"] for s in plan)
    return f"{trigger_event} on {target}: {len(plan)} action(s) proposed ({actions_summary})."


def _severity_for(plan: List[Dict[str, Any]], trigger_event: str) -> str:
    if any(s["risk_score"] >= 70 for s in plan):
        return "critical"
    if trigger_event in ("sla.violation", "provider.unhealthy", "guardrail.violation"):
        return "warning"
    if trigger_event == "budget.exceeded":
        return "critical"
    return "info"
