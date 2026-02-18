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
from pathlib import Path
from typing import Optional

import asyncpg
import deps
import httpx
import redis.asyncio as aioredis
from alembic import command
from alembic.config import Config
from auth import LoginRequest, TokenResponse, UserInfo, get_current_user, login
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from routers import agents as agents_router
from routers import budgets as budgets_router
from routers import guardrails as guardrails_router
from routers import keys as keys_router
from routers import mcp_servers as mcp_servers_router
from routers import models as models_router
from routers import reports as reports_router
from routers import settings as settings_router
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
LITELLM_MASTER_KEY = os.getenv("LITELLM_MASTER_KEY", "$LITELLM_KEY")
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


app = FastAPI(
    title="AI Control Plane Admin API",
    description="Administrative API for managing the AI Control Plane platform",
    version="1.0.0",
    lifespan=lifespan,
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8086)
