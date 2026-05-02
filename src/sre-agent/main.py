"""SRE Agent service.

Receives incident triggers via /webhook (called by admin-api event publisher
when an event subscription has channel='sre_workflow'). Runs diagnose+
propose, persists incident with status='awaiting_approval', dispatches
notifications. Approval and execution happen through admin-api proxy
endpoints calling /incidents/{id}/execute and /incidents/{id}/reject.
"""

import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import agent
import asyncpg
import httpx
from admin_client import AdminClient, build_admin_client
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from llm import LLMProposer, build_proposer
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import BaseModel, Field

from shared.cors import get_cors_origins
from shared.middleware import ServiceAuthMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


db_pool: Optional[asyncpg.Pool] = None
http_client: Optional[httpx.AsyncClient] = None
admin_client: Optional[AdminClient] = None
proposer: Optional[LLMProposer] = None


class IncidentTrigger(BaseModel):
    event_type: str = Field(..., description="Event type that opened the incident.")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Event payload.")


class ApproveRequest(BaseModel):
    approver: str = Field(..., description="User id of the approver.")


class RejectRequest(BaseModel):
    approver: str = Field(..., description="User id of the rejecter.")
    reason: Optional[str] = Field(None, description="Free-text reason for rejection.")


class InvokeRequest(BaseModel):
    capability: str = Field(..., description="A2A capability name.")
    input: Dict[str, Any] = Field(default_factory=dict)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool, http_client, admin_client, proposer

    otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
    resource = Resource.create({"service.name": "sre-agent"})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=otel_endpoint, insecure=True)))
    trace.set_tracer_provider(provider)

    http_client = httpx.AsyncClient(timeout=30.0)

    database_url = os.getenv("DATABASE_URL")
    if database_url:
        try:
            db_pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)
            logger.info("Database pool established")
        except Exception as e:
            logger.warning("Could not connect to database: %s", e)

    admin_client = build_admin_client()
    proposer = build_proposer()

    logger.info(
        "SRE agent started (model=%s, auto_approve=%s, threshold=%s)",
        os.getenv("SRE_AGENT_MODEL", "claude-sonnet-4-6"),
        os.getenv("SRE_AUTO_APPROVE", "false"),
        os.getenv("SRE_RISK_THRESHOLD", "40"),
    )
    yield

    if http_client:
        await http_client.aclose()
    if admin_client:
        await admin_client.aclose()
    if db_pool:
        await db_pool.close()
    logger.info("SRE agent stopped")


app = FastAPI(
    title="SRE Agent",
    description="LLM-driven SRE incident response for the AI Gateway control plane.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    ServiceAuthMiddleware,
    unauthenticated_paths={"/health", "/ready", "/healthz"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Service-Key"],
)

FastAPIInstrumentor.instrument_app(app)


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "db": db_pool is not None,
        "model": os.getenv("SRE_AGENT_MODEL", "claude-sonnet-4-6"),
    }


async def _kick_off_diagnosis(incident_id: str) -> None:
    if not db_pool or not proposer or not http_client:
        logger.warning("SRE agent not fully initialized; skipping diagnosis")
        return
    try:
        await agent.diagnose_and_propose(db_pool, http_client, proposer, incident_id)
    except Exception as e:
        logger.exception("Diagnose+propose failed for %s: %s", incident_id, e)
        try:
            async with db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE sre_incidents SET status = 'closed_failed', outcome_summary = $1, closed_at = NOW() WHERE id = $2::uuid",
                    f"diagnose_and_propose error: {e}",
                    incident_id,
                )
        except Exception:
            pass


@app.post("/webhook")
async def receive_event(trigger: IncidentTrigger, background: BackgroundTasks) -> Dict[str, str]:
    """Open an incident and run diagnose+propose in the background."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    incident_id = await agent.open_incident(db_pool, trigger.event_type, trigger.payload)
    background.add_task(_kick_off_diagnosis, incident_id)
    return {"incident_id": incident_id, "status": "open"}


@app.post("/trigger")
async def manual_trigger(trigger: IncidentTrigger, background: BackgroundTasks) -> Dict[str, str]:
    """Manual trigger endpoint for the admin UI test path."""
    return await receive_event(trigger, background)


@app.get("/incidents")
async def list_incidents(status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    async with db_pool.acquire() as conn:
        if status:
            rows = await conn.fetch(
                """
                SELECT id, trigger_event, status, outcome_summary, opened_at, closed_at,
                       jsonb_array_length(COALESCE(proposed_plan, '[]'::jsonb)) AS plan_count,
                       jsonb_array_length(COALESCE(executed_actions, '[]'::jsonb)) AS executed_count
                FROM sre_incidents
                WHERE status = $1
                ORDER BY opened_at DESC
                LIMIT $2
                """,
                status,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, trigger_event, status, outcome_summary, opened_at, closed_at,
                       jsonb_array_length(COALESCE(proposed_plan, '[]'::jsonb)) AS plan_count,
                       jsonb_array_length(COALESCE(executed_actions, '[]'::jsonb)) AS executed_count
                FROM sre_incidents
                ORDER BY opened_at DESC
                LIMIT $1
                """,
                limit,
            )
    return [
        {
            "id": str(r["id"]),
            "trigger_event": r["trigger_event"],
            "status": r["status"],
            "outcome_summary": r["outcome_summary"],
            "opened_at": r["opened_at"].isoformat() if r["opened_at"] else None,
            "closed_at": r["closed_at"].isoformat() if r["closed_at"] else None,
            "plan_count": r["plan_count"],
            "executed_count": r["executed_count"],
        }
        for r in rows
    ]


@app.get("/incidents/{incident_id}")
async def get_incident(incident_id: str) -> Dict[str, Any]:
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM sre_incidents WHERE id = $1::uuid",
            incident_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Incident not found")
        decisions = await conn.fetch(
            "SELECT * FROM sre_action_decisions WHERE incident_id = $1::uuid ORDER BY created_at",
            incident_id,
        )
    return _incident_dict(row, decisions)


@app.post("/incidents/{incident_id}/execute")
async def execute(incident_id: str, body: ApproveRequest) -> Dict[str, Any]:
    if not db_pool or not admin_client or not http_client:
        raise HTTPException(status_code=503, detail="SRE agent not initialized")
    return await agent.execute_approved(db_pool, admin_client, http_client, incident_id, body.approver)


@app.post("/incidents/{incident_id}/reject")
async def reject(incident_id: str, body: RejectRequest) -> Dict[str, Any]:
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    return await agent.reject_incident(db_pool, incident_id, body.approver, body.reason)


@app.get("/stats")
async def stats() -> Dict[str, Any]:
    """Last-30-day counts for the UI Stats tab."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT status, COUNT(*) AS n
            FROM sre_incidents
            WHERE opened_at > NOW() - INTERVAL '30 days'
            GROUP BY status
            """,
        )
        mttr_seconds = await conn.fetchval(
            """
            SELECT EXTRACT(EPOCH FROM AVG(closed_at - opened_at))
            FROM sre_incidents
            WHERE opened_at > NOW() - INTERVAL '30 days' AND closed_at IS NOT NULL
            """,
        )
    counts = {r["status"]: r["n"] for r in rows}
    return {
        "by_status": counts,
        "mttr_seconds": float(mttr_seconds) if mttr_seconds is not None else None,
    }


@app.post("/invoke")
async def a2a_invoke(req: InvokeRequest, background: BackgroundTasks) -> Dict[str, Any]:
    """A2A capability dispatcher (for future Temporal supervisor wrapping).

    v1 supports two capabilities:
    - `handle_incident` — equivalent to /webhook; opens an incident and kicks off diagnosis.
    - `coordinate` — returns a 'complete' decision so a SupervisorAgentWorkflow exits cleanly.
    """
    cap = req.capability
    if cap == "handle_incident":
        trigger = IncidentTrigger(
            event_type=req.input.get("trigger_event") or req.input.get("event_type", "unknown"),
            payload=req.input.get("payload") or req.input,
        )
        result = await receive_event(trigger, background)
        return {"result": result, "tokens_used": 0}
    if cap == "coordinate":
        return {"result": {"action": "complete", "result": "delegated to webhook flow"}, "tokens_used": 0}
    return {"result": {"error": f"Unknown capability: {cap}"}, "tokens_used": 0}


def _incident_dict(row, decisions) -> Dict[str, Any]:
    return {
        "id": str(row["id"]),
        "trigger_event": row["trigger_event"],
        "trigger_payload": _maybe_json(row["trigger_payload"]),
        "correlation_id": str(row["correlation_id"]) if row["correlation_id"] else None,
        "workflow_id": row["workflow_id"],
        "diagnosis": _maybe_json(row["diagnosis"]),
        "proposed_plan": _maybe_json(row["proposed_plan"]),
        "executed_actions": _maybe_json(row["executed_actions"]),
        "status": row["status"],
        "outcome_summary": row["outcome_summary"],
        "opened_at": row["opened_at"].isoformat() if row["opened_at"] else None,
        "closed_at": row["closed_at"].isoformat() if row["closed_at"] else None,
        "decisions": [
            {
                "id": str(d["id"]),
                "action": d["action"],
                "params": _maybe_json(d["params"]),
                "risk_score": d["risk_score"],
                "decision": d["decision"],
                "approved_by": d["approved_by"],
                "executed_at": d["executed_at"].isoformat() if d["executed_at"] else None,
                "success": d["success"],
                "error": d["error"],
            }
            for d in decisions
        ],
    }


def _maybe_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8092)
