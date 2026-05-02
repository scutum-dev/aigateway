"""Landing backend: receives demo requests from the public landing page.

Single-purpose FastAPI service. Hardened for public exposure:
- Honeypot field rejected silently
- Per-IP rate limit (in-memory; fine for low-volume marketing surface)
- All inputs Pydantic-validated; emails normalized
- DB persistence is the durable record. Cal.com booking + SMTP alert are best-effort.
"""

import logging
import os
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import Any, Deque, Dict, Optional

import asyncpg
import calcom
import email_sender
import httpx
import storage
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import BaseModel, EmailStr, Field, field_validator

from shared.cors import get_cors_origins

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


db_pool: Optional[asyncpg.Pool] = None
http_client: Optional[httpx.AsyncClient] = None

# Per-IP rate limit: at most N requests per WINDOW seconds. In-memory is fine
# for a marketing surface; revisit if traffic justifies Redis-backed limiting.
RATE_LIMIT_MAX = int(os.getenv("DEMO_RATE_LIMIT_MAX", "5"))
RATE_LIMIT_WINDOW_S = int(os.getenv("DEMO_RATE_LIMIT_WINDOW_S", "3600"))
_ip_hits: Dict[str, Deque[float]] = defaultdict(deque)


class PreferredWindow(BaseModel):
    date: Optional[str] = Field(None, description="ISO date (YYYY-MM-DD)")
    time_of_day: Optional[str] = Field(None, description="morning|afternoon|evening")
    timezone: Optional[str] = Field(None, description="IANA tz, e.g. America/Los_Angeles")
    start_iso: Optional[str] = Field(None, description="ISO 8601 start; if set we attempt Cal.com booking")
    end_iso: Optional[str] = Field(None, description="ISO 8601 end")


class DemoRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    work_email: EmailStr = Field(..., description="Work email of the requester")
    company: Optional[str] = Field(None, max_length=200)
    role: Optional[str] = Field(None, max_length=120)
    team_size: Optional[str] = Field(None, max_length=40)
    use_case: Optional[str] = Field(None, max_length=4000)
    preferred_window: Optional[PreferredWindow] = None
    company_field: Optional[str] = Field(None, description="HONEYPOT — must be empty")

    @field_validator("name", "company", "role", "team_size", "use_case")
    @classmethod
    def strip_strings(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if isinstance(v, str) else v


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool, http_client

    otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
    resource = Resource.create({"service.name": "landing-backend"})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=otel_endpoint, insecure=True)))
    trace.set_tracer_provider(provider)

    http_client = httpx.AsyncClient(timeout=30.0)

    database_url = os.getenv("DATABASE_URL")
    if database_url:
        try:
            db_pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)
            logger.info("DB pool established")
        except Exception as e:
            logger.warning("Could not connect to database: %s", e)

    logger.info(
        "landing-backend started (calcom_configured=%s, smtp_configured=%s)",
        calcom.is_configured(),
        email_sender.is_configured(),
    )
    yield

    if http_client:
        await http_client.aclose()
    if db_pool:
        await db_pool.close()
    logger.info("landing-backend stopped")


app = FastAPI(
    title="Landing Backend",
    description="Public-facing endpoint for landing-page demo requests. Persists, books via Cal.com, alerts founder.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for the landing page itself; nginx already proxies same-origin so this
# is a defensive safety net for cross-origin previews.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

FastAPIInstrumentor.instrument_app(app)


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "db": db_pool is not None,
        "calcom_configured": calcom.is_configured(),
        "smtp_configured": email_sender.is_configured(),
    }


@app.get("/api/demo-availability")
async def availability(
    date_from: str = Query(..., description="ISO date YYYY-MM-DD"),
    date_to: str = Query(..., description="ISO date YYYY-MM-DD"),
) -> Dict[str, Any]:
    """Slot picker data source for the landing form."""
    if not http_client:
        raise HTTPException(status_code=503, detail="HTTP client not initialized")
    return await calcom.get_availability(http_client, date_from, date_to)


def _check_rate_limit(ip: str) -> None:
    now = time.monotonic()
    cutoff = now - RATE_LIMIT_WINDOW_S
    hits = _ip_hits[ip]
    while hits and hits[0] < cutoff:
        hits.popleft()
    if len(hits) >= RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="Too many requests")
    hits.append(now)


@app.post("/api/demo-request")
async def submit(
    body: DemoRequest,
    request: Request,
    background: BackgroundTasks,
) -> Dict[str, Any]:
    """Persist a demo request, optionally book a Cal.com slot, alert founder."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    if body.company_field:
        # Honeypot tripped — silently look like success so the bot doesn't retry.
        logger.info("Demo request honeypot tripped from %s", request.client.host if request.client else "?")
        return {"ok": True, "id": "honeypot"}

    ip = request.client.host if request.client else "unknown"
    _check_rate_limit(ip)
    user_agent = request.headers.get("user-agent", "")[:500]

    request_id = await storage.insert_demo_request(
        db_pool,
        name=body.name,
        work_email=str(body.work_email).lower(),
        company=body.company,
        role=body.role,
        team_size=body.team_size,
        use_case=body.use_case,
        preferred_window=body.preferred_window.model_dump() if body.preferred_window else None,
        source_ip=ip,
        user_agent=user_agent,
    )

    booking_url: Optional[str] = None
    booking_status: str = "not_attempted"
    pw = body.preferred_window
    if pw and pw.start_iso and pw.end_iso and calcom.is_configured():
        result = await calcom.create_booking(
            http_client,
            name=body.name,
            email=str(body.work_email),
            start_iso=pw.start_iso,
            end_iso=pw.end_iso,
            notes=body.use_case,
            timezone=pw.timezone or "UTC",
        )
        if result["ok"]:
            await storage.attach_calcom_booking(db_pool, request_id, result["booking_id"], result.get("meeting_url"))
            booking_url = result.get("meeting_url")
            booking_status = "scheduled"
        else:
            booking_status = f"failed: {result.get('error', 'unknown')}"

    background.add_task(
        _fire_internal_alert,
        request_id,
        body.model_dump(exclude={"company_field"}),
        ip,
        booking_url,
    )

    return {
        "ok": True,
        "id": request_id,
        "booking_status": booking_status,
        "meeting_url": booking_url,
        "message": (
            "Booked! Check your inbox for the meeting invite."
            if booking_url
            else "Got it — we'll reach out within 24 hours."
        ),
    }


async def _fire_internal_alert(
    request_id: str,
    body: Dict[str, Any],
    source_ip: str,
    booking_url: Optional[str],
) -> None:
    payload = {
        "id": request_id,
        "name": body.get("name"),
        "work_email": str(body.get("work_email") or ""),
        "company": body.get("company"),
        "role": body.get("role"),
        "team_size": body.get("team_size"),
        "use_case": body.get("use_case"),
        "preferred_window": body.get("preferred_window"),
        "calcom_meeting_url": booking_url,
        "source_ip": source_ip,
    }
    try:
        await email_sender.send_internal_alert(payload)
    except Exception as e:
        logger.warning("Internal alert failed for %s: %s", request_id, e)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8093)
