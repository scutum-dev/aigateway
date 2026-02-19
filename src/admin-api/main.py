"""
Admin API Service

A FastAPI service providing administrative endpoints for the AI Control Plane platform.

Features:
- JWT authentication (validates against LiteLLM API keys)
- Guardrail configuration and monitoring
- FinOps cost reporting
- MCP server configuration
- Workflow template management
- Platform settings
"""

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import asyncpg
import deps
import httpx
import redis.asyncio as aioredis
from alembic import command
from alembic.config import Config
from auth import LoginRequest, TokenResponse, UserInfo, get_current_user, login
from event_publisher import publish_event
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from routers import ab_tests as ab_tests_router
from routers import agents as agents_router
from routers import audit as audit_router
from routers import budgets as budgets_router
from routers import cache as cache_router
from routers import chargeback as chargeback_router
from routers import deprecations as deprecations_router
from routers import dlp as dlp_router
from routers import events as events_router
from routers import guardrails as guardrails_router
from routers import keys as keys_router
from routers import mcp_servers as mcp_servers_router
from routers import model_access as model_access_router
from routers import models as models_router
from routers import organizations as organizations_router
from routers import playground as playground_router
from routers import prompts as prompts_router
from routers import rate_limits as rate_limits_router
from routers import reports as reports_router
from routers import routing as routing_router
from routers import settings as settings_router
from routers import sla as sla_router
from routers import sso as sso_router
from routers import teams as teams_router
from routers import workflows as workflows_router
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://litellm:litellm@localhost:5432/litellm")
LITELLM_URL = os.getenv("LITELLM_URL", "http://localhost:4000")
LITELLM_MASTER_KEY = os.getenv("LITELLM_MASTER_KEY", "")
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Request size limit (1MB default, configurable)
MAX_REQUEST_SIZE = int(os.getenv("MAX_REQUEST_SIZE_BYTES", 1_048_576))  # 1MB


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to limit request body size and prevent DoS attacks."""

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            if int(content_length) > MAX_REQUEST_SIZE:
                return Response(
                    content='{"detail": "Request body too large"}', status_code=413, media_type="application/json"
                )
        return await call_next(request)


class GracefulShutdownMiddleware(BaseHTTPMiddleware):
    """Middleware to track active requests for graceful shutdown."""

    async def dispatch(self, request: Request, call_next):
        global active_requests

        # Reject new requests during shutdown (except health checks)
        if shutdown_event and shutdown_event.is_set():
            if request.url.path not in ["/health", "/healthz", "/ready"]:
                return Response(
                    content='{"detail": "Service is shutting down"}', status_code=503, media_type="application/json"
                )

        # Track active requests
        active_requests += 1
        try:
            return await call_next(request)
        finally:
            active_requests -= 1


# Rate limit cache
_rate_limit_cache: dict = {"value": None, "expires_at": 0.0}

# In-memory fallback for rate limiting (single-instance only)
_inmemory_requests: list = []


async def _get_global_rate_limit() -> Optional[int]:
    """Read global_rate_limit from platform_settings DB, cached for 60s."""
    now = time.time()
    if _rate_limit_cache["value"] is not None and now < _rate_limit_cache["expires_at"]:
        return _rate_limit_cache["value"]

    if not deps.db_pool:
        return None

    try:
        async with deps.db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT value FROM platform_settings WHERE key = 'global_rate_limit'")
            if row:
                val = json.loads(row["value"])
                limit = int(val) if val else None
            else:
                limit = None
        _rate_limit_cache["value"] = limit
        _rate_limit_cache["expires_at"] = now + 60.0
        return limit
    except Exception as e:
        logger.warning(f"Could not read rate limit setting: {e}")
        return _rate_limit_cache.get("value")


class GlobalRateLimitMiddleware(BaseHTTPMiddleware):
    """Enforce global_rate_limit from platform_settings using Redis sliding window."""

    EXEMPT_PATHS = {"/health", "/healthz", "/ready", "/auth/login"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        limit = await _get_global_rate_limit()
        if not limit:
            return await call_next(request)

        now = time.time()
        window_start = now - 60.0
        remaining = limit

        # Try Redis sliding window
        if deps.redis_client:
            try:
                key = "rate_limit:global"
                pipe = deps.redis_client.pipeline()
                pipe.zremrangebyscore(key, 0, window_start)
                pipe.zadd(key, {f"{now}": now})
                pipe.zcard(key)
                pipe.expire(key, 120)
                results = await pipe.execute()
                count = results[2]
                remaining = max(0, limit - count)

                if count > limit:
                    return Response(
                        content=json.dumps({"detail": "Rate limit exceeded"}),
                        status_code=429,
                        media_type="application/json",
                        headers={
                            "Retry-After": "60",
                            "X-RateLimit-Limit": str(limit),
                            "X-RateLimit-Remaining": "0",
                        },
                    )

                response = await call_next(request)
                response.headers["X-RateLimit-Limit"] = str(limit)
                response.headers["X-RateLimit-Remaining"] = str(remaining)
                return response
            except Exception as e:
                logger.warning(f"Redis rate limit error, failing open: {e}")

        # In-memory fallback (single-instance only)
        _inmemory_requests[:] = [t for t in _inmemory_requests if t > window_start]
        _inmemory_requests.append(now)
        count = len(_inmemory_requests)
        remaining = max(0, limit - count)

        if count > limit:
            return Response(
                content=json.dumps({"detail": "Rate limit exceeded"}),
                status_code=429,
                media_type="application/json",
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response


from shared.cors import get_cors_origins  # noqa: E402

# Graceful shutdown state
shutdown_event: Optional[asyncio.Event] = None
active_requests: int = 0
SHUTDOWN_TIMEOUT = int(os.getenv("SHUTDOWN_TIMEOUT_SECONDS", 30))


async def _sync_gateway_config_on_startup():
    """Write gateway config from DB to shared volume so agentgateway can start."""
    from gateway_sync import GATEWAY_CONFIG_PATH, build_gateway_config

    if not GATEWAY_CONFIG_PATH or not deps.db_pool:
        return
    try:
        async with deps.db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM mcp_servers WHERE is_active = true ORDER BY name")
            servers = [
                {
                    "name": row["name"],
                    "server_type": row["server_type"],
                    "command": row["command"],
                    "url": row["url"],
                    "args": row["args"] or [],
                    "env": json.loads(row["env"]) if isinstance(row["env"], str) else (row["env"] or {}),
                }
                for row in rows
            ]

            agent_rows = await conn.fetch("SELECT * FROM a2a_agents WHERE is_active = true ORDER BY name")
            agents = [{"name": r["name"], "url": r["url"]} for r in agent_rows]

        config_yaml = build_gateway_config(servers, agents)
        os.makedirs(os.path.dirname(GATEWAY_CONFIG_PATH), exist_ok=True)
        with open(GATEWAY_CONFIG_PATH, "w") as f:
            f.write(config_yaml)
        logger.info("Wrote initial gateway config (%d MCP servers, %d A2A agents)", len(servers), len(agents))
    except Exception as e:
        logger.warning("Could not sync gateway config on startup: %s", e)


async def _sla_health_collector():
    """Background task: collect provider health metrics every 5 minutes."""
    await asyncio.sleep(30)  # Wait for startup to complete
    while True:
        try:
            if deps.db_pool:
                async with deps.db_pool.acquire() as conn:
                    # Check if LiteLLM_SpendLogs table exists
                    table_exists = await conn.fetchval(
                        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'LiteLLM_SpendLogs')"
                    )
                    if not table_exists:
                        logger.debug("LiteLLM_SpendLogs table not found, skipping health collection")
                        await asyncio.sleep(300)
                        continue

                    # Aggregate metrics from last 5 minutes
                    metrics = await conn.fetch("""
                        SELECT
                            COALESCE(SPLIT_PART(model, '/', 1), 'unknown') AS provider,
                            model,
                            COUNT(*) AS request_count,
                            COUNT(*) FILTER (WHERE status != 'success') AS error_count,
                            PERCENTILE_CONT(0.50) WITHIN GROUP (
                                ORDER BY EXTRACT(EPOCH FROM ("endTime" - "startTime")) * 1000
                            )::int AS p50_latency_ms,
                            PERCENTILE_CONT(0.95) WITHIN GROUP (
                                ORDER BY EXTRACT(EPOCH FROM ("endTime" - "startTime")) * 1000
                            )::int AS p95_latency_ms,
                            PERCENTILE_CONT(0.99) WITHIN GROUP (
                                ORDER BY EXTRACT(EPOCH FROM ("endTime" - "startTime")) * 1000
                            )::int AS p99_latency_ms,
                            AVG(EXTRACT(EPOCH FROM ("endTime" - "startTime")) * 1000)::int AS avg_latency_ms,
                            COALESCE(SUM("completionTokens" + "promptTokens"), 0)::int AS total_tokens,
                            COALESCE(SUM(spend), 0) AS total_cost
                        FROM "LiteLLM_SpendLogs"
                        WHERE "startTime" >= NOW() - INTERVAL '5 minutes'
                          AND "endTime" IS NOT NULL
                          AND "startTime" IS NOT NULL
                        GROUP BY model
                    """)

                    bucket_start = datetime.now(timezone.utc).replace(second=0, microsecond=0)

                    for m in metrics:
                        # Insert health metric
                        await conn.execute(
                            """
                            INSERT INTO provider_health_metrics
                                (provider, model, bucket_start, request_count, error_count,
                                 p50_latency_ms, p95_latency_ms, p99_latency_ms, avg_latency_ms,
                                 total_tokens, total_cost)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                            ON CONFLICT (provider, model, bucket_start) DO UPDATE SET
                                request_count = EXCLUDED.request_count,
                                error_count = EXCLUDED.error_count,
                                p50_latency_ms = EXCLUDED.p50_latency_ms,
                                p95_latency_ms = EXCLUDED.p95_latency_ms,
                                p99_latency_ms = EXCLUDED.p99_latency_ms,
                                avg_latency_ms = EXCLUDED.avg_latency_ms,
                                total_tokens = EXCLUDED.total_tokens,
                                total_cost = EXCLUDED.total_cost
                        """,
                            m["provider"],
                            m["model"],
                            bucket_start,
                            m["request_count"],
                            m["error_count"],
                            m["p50_latency_ms"],
                            m["p95_latency_ms"],
                            m["p99_latency_ms"],
                            m["avg_latency_ms"],
                            m["total_tokens"],
                            m["total_cost"],
                        )

                    # Check SLA definitions for violations
                    sla_defs = await conn.fetch("SELECT * FROM sla_definitions WHERE is_active = true")

                    for sla in sla_defs:
                        # Find matching metrics
                        for m in metrics:
                            model_match = (
                                not sla["model_pattern"]
                                or sla["model_pattern"] == "*"
                                or m["model"].startswith(sla["model_pattern"].replace("*", ""))
                            )
                            provider_match = not sla["provider"] or m["provider"] == sla["provider"]
                            if not (model_match and provider_match):
                                continue

                            violations = []
                            if (
                                sla["target_p95_ms"]
                                and m["p95_latency_ms"]
                                and m["p95_latency_ms"] > sla["target_p95_ms"]
                            ):
                                violations.append(
                                    ("latency_p95", float(sla["target_p95_ms"]), float(m["p95_latency_ms"]))
                                )
                            if (
                                sla["target_p99_ms"]
                                and m["p99_latency_ms"]
                                and m["p99_latency_ms"] > sla["target_p99_ms"]
                            ):
                                violations.append(
                                    ("latency_p99", float(sla["target_p99_ms"]), float(m["p99_latency_ms"]))
                                )

                            error_rate = m["error_count"] / m["request_count"] if m["request_count"] > 0 else 0
                            if sla["target_error_rate"] and error_rate > float(sla["target_error_rate"]):
                                violations.append(("error_rate", float(sla["target_error_rate"]), error_rate))

                            for v_type, threshold, actual in violations:
                                await conn.execute(
                                    """
                                    INSERT INTO sla_violations (sla_definition_id, provider, model, violation_type, threshold_value, actual_value)
                                    VALUES ($1, $2, $3, $4, $5, $6)
                                """,
                                    sla["id"],
                                    m["provider"],
                                    m["model"],
                                    v_type,
                                    threshold,
                                    actual,
                                )
                                # Publish event
                                await publish_event(
                                    deps.db_pool,
                                    "sla.violation",
                                    {
                                        "sla_name": sla["name"],
                                        "provider": m["provider"],
                                        "model": m["model"],
                                        "violation_type": v_type,
                                        "threshold": threshold,
                                        "actual": actual,
                                    },
                                    source_service="sla-health-collector",
                                    http_client=deps.http_client,
                                )

                    if metrics:
                        logger.info("SLA health collected: %d provider/model combos", len(metrics))

        except Exception as e:
            logger.warning("SLA health collector error: %s", e)

        await asyncio.sleep(300)  # 5 minutes


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with graceful shutdown."""
    global shutdown_event, active_requests

    # Initialize shutdown event
    shutdown_event = asyncio.Event()

    # Setup OpenTelemetry
    resource = Resource.create({"service.name": "admin-api"})
    provider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=OTEL_ENDPOINT))
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    # Run Alembic migrations
    _run_migrations()

    # Create database pool
    try:
        deps.db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
        logger.info("Database connection established")
    except Exception as e:
        logger.warning(f"Could not connect to database: {e}")

    # Create HTTP client
    deps.http_client = httpx.AsyncClient(timeout=30.0)

    # Connect to Redis (for rate limiting)
    try:
        deps.redis_client = aioredis.from_url(REDIS_URL, decode_responses=False)
        await deps.redis_client.ping()
        logger.info("Redis connection established (rate limiting enabled)")
    except Exception as e:
        logger.warning(f"Could not connect to Redis: {e} (rate limiting will use in-memory fallback)")
        deps.redis_client = None

    # Sync gateway config from DB to shared volume (so agentgateway can start)
    await _sync_gateway_config_on_startup()

    # Start background tasks
    _bg_tasks = []
    _bg_tasks.append(asyncio.create_task(_sla_health_collector()))
    logger.info("Background tasks started (SLA health collector)")

    logger.info("Admin API service started")
    yield

    # Graceful shutdown
    logger.info("Initiating graceful shutdown...")
    shutdown_event.set()

    # Wait for active requests to complete (with timeout)
    shutdown_start = asyncio.get_event_loop().time()
    while active_requests > 0:
        if asyncio.get_event_loop().time() - shutdown_start > SHUTDOWN_TIMEOUT:
            logger.warning(f"Shutdown timeout reached with {active_requests} requests still active")
            break
        logger.info(f"Waiting for {active_requests} active requests to complete...")
        await asyncio.sleep(0.5)

    # Cancel background tasks
    for task in _bg_tasks:
        task.cancel()

    # Flush OpenTelemetry spans
    try:
        provider.force_flush(timeout_millis=5000)
    except Exception as e:
        logger.warning(f"Error flushing traces: {e}")

    # Cleanup resources
    if deps.redis_client:
        await deps.redis_client.close()
    if deps.http_client:
        await deps.http_client.aclose()
    if deps.db_pool:
        await deps.db_pool.close()

    # Clear deps references
    deps.db_pool = None
    deps.http_client = None
    deps.redis_client = None

    logger.info("Admin API service stopped gracefully")


def _run_migrations():
    """Run Alembic migrations on startup."""
    try:
        # Get the directory where this file lives
        base_path = Path(__file__).parent
        alembic_cfg = Config(str(base_path / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(base_path / "alembic"))
        alembic_cfg.set_main_option("sqlalchemy.url", DATABASE_URL)

        # Run migrations
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations completed")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


openapi_tags = [
    {
        "name": "MCP Servers",
        "description": "Manage MCP (Model Context Protocol) server backends and sync config to Agent Gateway.",
    },
    {"name": "Agents", "description": "Manage A2A (Agent-to-Agent) agent registrations and lifecycle."},
    {
        "name": "Workflows",
        "description": "LangGraph workflow templates (research, coding, data-analysis) and execution management.",
    },
    {"name": "Settings", "description": "Platform-wide settings: rate limits, feature flags, maintenance mode."},
    {
        "name": "Guardrails",
        "description": "Content safety guardrails: PII detection (Presidio), input/output scanning (LLM Guard), per-team profiles.",
    },
    {
        "name": "Reports",
        "description": "FinOps cost reports, usage trends, and CSV/JSON export from LiteLLM spend logs.",
    },
    {"name": "API Keys", "description": "LiteLLM API key provisioning, rotation, and per-key spend tracking."},
    {"name": "Models", "description": "Model catalog, provider configuration, and deployment status."},
    {"name": "Teams", "description": "Team management: create teams, assign members, set budgets and model access."},
    {"name": "Budgets", "description": "Team and organization budget limits with soft/hard thresholds."},
    {
        "name": "Organizations",
        "description": "Multi-tenancy: Organization → Business Unit → Team hierarchy, membership, and RBAC.",
    },
    {"name": "SSO", "description": "Single sign-on configuration: OIDC/SAML providers per organization."},
    {"name": "Audit", "description": "Immutable audit trail of all administrative actions with filtering and export."},
    {
        "name": "DLP",
        "description": "Data Loss Prevention: content detectors (regex, keyword, PII), team content policies.",
    },
    {
        "name": "Prompts",
        "description": "Versioned prompt template registry with approval workflows, rendering, and LLM execution.",
    },
    {
        "name": "Rate Limits",
        "description": "Granular rate limit policies per user/team/model with RPM, TPM, daily limits, and burst.",
    },
    {
        "name": "Model Access",
        "description": "Tiered model access governance with request/approval workflows and time-limited grants.",
    },
    {
        "name": "Chargeback",
        "description": "Cost allocation rules, monthly chargeback reports from real spend data, and budget forecasting.",
    },
    {
        "name": "SLA",
        "description": "SLA definitions, provider health metrics collection, violation detection, and failover rules.",
    },
    {
        "name": "A/B Tests",
        "description": "Model A/B testing: variant registration, traffic splitting, metric snapshots, promote/rollback.",
    },
    {
        "name": "Cache",
        "description": "Semantic cache management: stats, entry lookup, settings sync to LiteLLM Redis cache.",
    },
    {
        "name": "Events",
        "description": "Event subscription system: webhook, Slack, email, PagerDuty channels with event log.",
    },
    {
        "name": "Playground",
        "description": "Shareable playground sessions: prompt/model/settings persistence and sharing.",
    },
    {"name": "Deprecations", "description": "Model deprecation notices with replacement suggestions and sunset dates."},
]

app = FastAPI(
    title="AI Control Plane Admin API",
    description="Administrative API for managing the AI Control Plane platform",
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=openapi_tags,
)

# Add graceful shutdown middleware (tracks active requests)
app.add_middleware(GracefulShutdownMiddleware)

# Add global rate limit middleware (enforces platform_settings.global_rate_limit)
app.add_middleware(GlobalRateLimitMiddleware)

# Add request size limit middleware
app.add_middleware(RequestSizeLimitMiddleware)

# Add CORS middleware with environment-specific origins
cors_origins = get_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

# Instrument with OpenTelemetry
FastAPIInstrumentor.instrument_app(app)


# =============================================================================
# Health & Auth Endpoints
# =============================================================================


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/auth/login", response_model=TokenResponse)
async def auth_login(request: LoginRequest):
    """Authenticate and get JWT token."""
    return await login(request)


@app.get("/auth/me", response_model=UserInfo)
async def get_me(user: UserInfo = Depends(get_current_user)):
    """Get current user info."""
    return user


# =============================================================================
# SSO Auth Endpoints
# =============================================================================

from auth_sso import list_sso_providers, sso_authorize, sso_callback  # noqa: E402


@app.get("/auth/sso/providers")
async def auth_sso_providers():
    """List available SSO providers."""
    return await list_sso_providers()


@app.get("/auth/sso/authorize/{org_slug}")
async def auth_sso_authorize(org_slug: str):
    """Redirect to IdP for SSO authentication."""
    return await sso_authorize(org_slug)


@app.get("/auth/sso/callback")
async def auth_sso_callback(code: str = "", state: str = ""):
    """Handle OIDC callback from IdP."""
    return await sso_callback(code=code, state=state)


# =============================================================================
# Include Routers
# =============================================================================

app.include_router(mcp_servers_router.router, prefix="/api/v1", tags=["MCP Servers"])
app.include_router(agents_router.router, prefix="/api/v1", tags=["Agents"])
app.include_router(workflows_router.router, prefix="/api/v1", tags=["Workflows"])
app.include_router(settings_router.router, prefix="/api/v1", tags=["Settings"])
app.include_router(guardrails_router.router, prefix="/api/v1", tags=["Guardrails"])
app.include_router(reports_router.router, prefix="/api/v1", tags=["Reports"])
app.include_router(keys_router.router, prefix="/api/v1", tags=["API Keys"])
app.include_router(models_router.router, prefix="/api/v1", tags=["Models"])
app.include_router(teams_router.router, prefix="/api/v1", tags=["Teams"])
app.include_router(budgets_router.router, prefix="/api/v1", tags=["Budgets"])
app.include_router(organizations_router.router, prefix="/api/v1", tags=["Organizations"])
app.include_router(sso_router.router, prefix="/api/v1", tags=["SSO"])
app.include_router(audit_router.router, prefix="/api/v1", tags=["Audit"])
app.include_router(dlp_router.router, prefix="/api/v1", tags=["DLP"])
app.include_router(prompts_router.router, prefix="/api/v1", tags=["Prompts"])
app.include_router(rate_limits_router.router, prefix="/api/v1", tags=["Rate Limits"])
app.include_router(model_access_router.router, prefix="/api/v1", tags=["Model Access"])
app.include_router(chargeback_router.router, prefix="/api/v1", tags=["Chargeback"])
app.include_router(sla_router.router, prefix="/api/v1", tags=["SLA"])
app.include_router(ab_tests_router.router, prefix="/api/v1", tags=["A/B Tests"])
app.include_router(cache_router.router, prefix="/api/v1", tags=["Cache"])
app.include_router(events_router.router, prefix="/api/v1", tags=["Events"])
app.include_router(playground_router.router, prefix="/api/v1", tags=["Playground"])
app.include_router(deprecations_router.router, prefix="/api/v1", tags=["Deprecations"])
app.include_router(routing_router.router, prefix="/api/v1", tags=["Routing"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8086)
