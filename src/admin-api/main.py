"""
Admin API Service

A FastAPI service providing administrative endpoints for the AI Control Plane platform.

Features:
- JWT authentication (validates against LiteLLM API keys)
- Model routing policy management
- Budget configuration and monitoring
- Team and user management
- MCP server configuration
- Workflow template management
- Real-time metrics
"""

import os
import logging
import json
import signal
import asyncio
from typing import Optional, List
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
import httpx
import asyncpg
from alembic.config import Config
from alembic import command

from auth import (
    login, LoginRequest, TokenResponse,
    get_current_user, require_admin, UserInfo
)
from models import (
    ModelConfig, ModelConfigUpdate,
    RoutingPolicy, RoutingPolicyCreate,
    Budget, BudgetCreate, BudgetUpdate,
    Team, TeamCreate, TeamUpdate, TeamMember,
    MCPServerConfig, MCPServerCreate, MCPServerUpdate,
    WorkflowSummary, WorkflowExecuteRequest, WorkflowExecutionSummary, WorkflowCreate,
    KeyGenerateRequest, KeyUpdateRequest, KeyDeleteRequest,
    RealtimeMetrics,
    PlatformSettings,
)
from gateway_sync import build_gateway_config, sync_configmap, restart_gateway

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://litellm:litellm@localhost:5432/litellm")
LITELLM_URL = os.getenv("LITELLM_URL", "http://localhost:4000")
LITELLM_MASTER_KEY = os.getenv("LITELLM_MASTER_KEY", "$LITELLM_KEY")
WORKFLOW_ENGINE_URL = os.getenv("WORKFLOW_ENGINE_URL", "http://localhost:8085")
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Request size limit (1MB default, configurable)
MAX_REQUEST_SIZE = int(os.getenv("MAX_REQUEST_SIZE_BYTES", 1_048_576))  # 1MB


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to limit request body size and prevent DoS attacks."""

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            if int(content_length) > MAX_REQUEST_SIZE:
                return Response(
                    content='{"detail": "Request body too large"}',
                    status_code=413,
                    media_type="application/json"
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
                    content='{"detail": "Service is shutting down"}',
                    status_code=503,
                    media_type="application/json"
                )

        # Track active requests
        active_requests += 1
        try:
            return await call_next(request)
        finally:
            active_requests -= 1


# CORS configuration - restrict in production
def get_cors_origins() -> list[str]:
    """Get allowed CORS origins based on environment."""
    if ENVIRONMENT == "production":
        # Production: only allow specific origins
        origins = os.getenv("CORS_ORIGINS", "").split(",")
        return [o.strip() for o in origins if o.strip()]
    # Development: allow localhost origins
    return [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

# Global resources
db_pool: Optional[asyncpg.Pool] = None
http_client: Optional[httpx.AsyncClient] = None

# Graceful shutdown state
shutdown_event: Optional[asyncio.Event] = None
active_requests: int = 0
SHUTDOWN_TIMEOUT = int(os.getenv("SHUTDOWN_TIMEOUT_SECONDS", 30))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with graceful shutdown."""
    global db_pool, http_client, shutdown_event

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
        db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
        logger.info("Database connection established")
    except Exception as e:
        logger.warning(f"Could not connect to database: {e}")

    # Create HTTP client
    http_client = httpx.AsyncClient(timeout=30.0)

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
    if http_client:
        await http_client.aclose()
    if db_pool:
        await db_pool.close()

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
# Model Configuration Endpoints
# =============================================================================

@app.get("/api/v1/models", response_model=List[ModelConfig])
async def list_models(user: UserInfo = Depends(get_current_user)):
    """List all model configurations."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM model_routing_config ORDER BY model_id")
        return [
            ModelConfig(
                model_id=row["model_id"],
                provider=row["provider"],
                tier=row["tier"],
                cost_per_1k_input=float(row["cost_per_1k_input"]),
                cost_per_1k_output=float(row["cost_per_1k_output"]),
                supports_streaming=row["supports_streaming"],
                supports_function_calling=row["supports_function_calling"],
                default_latency_sla_ms=row["default_latency_sla_ms"],
            )
            for row in rows
        ]


@app.put("/api/v1/models/{model_id}", response_model=ModelConfig)
async def update_model(
    model_id: str,
    update: ModelConfigUpdate,
    user: UserInfo = Depends(require_admin)
):
    """Update model configuration."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    updates = []
    params = []
    param_idx = 1

    for field, value in update.model_dump(exclude_unset=True).items():
        if value is not None:
            updates.append(f"{field} = ${param_idx}")
            params.append(value)
            param_idx += 1

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(model_id)

    async with db_pool.acquire() as conn:
        query = f"UPDATE model_routing_config SET {', '.join(updates)} WHERE model_id = ${param_idx} RETURNING *"
        row = await conn.fetchrow(query, *params)

        if not row:
            raise HTTPException(status_code=404, detail="Model not found")

        return ModelConfig(**dict(row))


# =============================================================================
# Routing Policy Endpoints
# =============================================================================

@app.get("/api/v1/routing-policies", response_model=List[RoutingPolicy])
async def list_routing_policies(user: UserInfo = Depends(get_current_user)):
    """List all routing policies."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM routing_policies ORDER BY priority DESC")
        return [
            RoutingPolicy(
                id=str(row["id"]),
                name=row["name"],
                description=row["description"],
                priority=row["priority"],
                condition=row["condition"],
                action=row["action"],
                target_models=row["target_models"],
                is_active=row["is_active"],
            )
            for row in rows
        ]


@app.post("/api/v1/routing-policies", response_model=RoutingPolicy)
async def create_routing_policy(
    policy: RoutingPolicyCreate,
    user: UserInfo = Depends(require_admin)
):
    """Create a new routing policy."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO routing_policies (name, description, priority, condition, action, target_models)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *
        """, policy.name, policy.description, policy.priority, policy.condition, policy.action, policy.target_models)

        return RoutingPolicy(
            id=str(row["id"]),
            name=row["name"],
            description=row["description"],
            priority=row["priority"],
            condition=row["condition"],
            action=row["action"],
            target_models=row["target_models"],
            is_active=row["is_active"],
        )


@app.delete("/api/v1/routing-policies/{policy_id}")
async def delete_routing_policy(
    policy_id: str,
    user: UserInfo = Depends(require_admin)
):
    """Delete a routing policy."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with db_pool.acquire() as conn:
        result = await conn.execute("DELETE FROM routing_policies WHERE id = $1", policy_id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Policy not found")

    return {"status": "deleted"}


# =============================================================================
# Budget Endpoints
# =============================================================================

def _row_to_budget(row) -> Budget:
    """Convert database row to Budget model."""
    return Budget(
        id=str(row["id"]),
        name=row["name"],
        entity_type=row["entity_type"],
        entity_id=row["entity_id"],
        monthly_limit=float(row["monthly_limit"]),
        current_spend=float(row["current_spend"]),
        soft_limit_percent=float(row["soft_limit_percent"]),
        hard_limit_percent=float(row["hard_limit_percent"]),
        alert_email=row["alert_email"],
        is_active=row["is_active"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@app.get("/api/v1/budgets", response_model=List[Budget])
async def list_budgets(user: UserInfo = Depends(get_current_user)):
    """List all budgets."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM budgets ORDER BY name")
        return [_row_to_budget(row) for row in rows]


@app.post("/api/v1/budgets", response_model=Budget)
async def create_budget(
    budget: BudgetCreate,
    user: UserInfo = Depends(require_admin)
):
    """Create a new budget."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO budgets (name, entity_type, entity_id, monthly_limit, soft_limit_percent, hard_limit_percent, alert_email)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
        """, budget.name, budget.entity_type, budget.entity_id, budget.monthly_limit,
            budget.soft_limit_percent, budget.hard_limit_percent, budget.alert_email)

        return _row_to_budget(row)


@app.put("/api/v1/budgets/{budget_id}", response_model=Budget)
async def update_budget(
    budget_id: str,
    update: BudgetUpdate,
    user: UserInfo = Depends(require_admin)
):
    """Update a budget."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    updates = []
    params = []
    param_idx = 1

    for field, value in update.model_dump(exclude_unset=True).items():
        if value is not None:
            updates.append(f"{field} = ${param_idx}")
            params.append(value)
            param_idx += 1

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(budget_id)

    async with db_pool.acquire() as conn:
        query = f"UPDATE budgets SET {', '.join(updates)} WHERE id = ${param_idx} RETURNING *"
        row = await conn.fetchrow(query, *params)

        if not row:
            raise HTTPException(status_code=404, detail="Budget not found")

        return _row_to_budget(row)


# =============================================================================
# Team Endpoints
# =============================================================================

@app.get("/api/v1/teams", response_model=List[Team])
async def list_teams(user: UserInfo = Depends(get_current_user)):
    """List all teams."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM teams ORDER BY name")
        teams = []
        for row in rows:
            members = await conn.fetch(
                "SELECT user_id FROM team_members WHERE team_id = $1",
                row["id"]
            )
            teams.append(Team(
                id=str(row["id"]),
                name=row["name"],
                description=row["description"],
                monthly_budget=float(row["monthly_budget"]) if row["monthly_budget"] else None,
                default_model=row["default_model"],
                members=[m["user_id"] for m in members],
                is_active=row["is_active"],
                created_at=row["created_at"],
            ))
        return teams


@app.post("/api/v1/teams", response_model=Team)
async def create_team(
    team: TeamCreate,
    user: UserInfo = Depends(require_admin)
):
    """Create a new team."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO teams (name, description, monthly_budget, default_model)
            VALUES ($1, $2, $3, $4)
            RETURNING *
        """, team.name, team.description, team.monthly_budget, team.default_model)

        return Team(
            id=str(row["id"]),
            name=row["name"],
            description=row["description"],
            monthly_budget=float(row["monthly_budget"]) if row["monthly_budget"] else None,
            default_model=row["default_model"],
            members=[],
            is_active=row["is_active"],
            created_at=row["created_at"],
        )


@app.post("/api/v1/teams/{team_id}/members")
async def add_team_member(
    team_id: str,
    member: TeamMember,
    user: UserInfo = Depends(require_admin)
):
    """Add a member to a team."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO team_members (team_id, user_id, role)
            VALUES ($1, $2, $3)
            ON CONFLICT (team_id, user_id) DO UPDATE SET role = $3
        """, team_id, member.user_id, member.role)

    return {"status": "added"}


# =============================================================================
# MCP Server Endpoints
# =============================================================================

def _parse_env(val) -> dict:
    """Parse env field which may be a dict (jsonb) or a JSON string."""
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _row_to_mcp(row) -> MCPServerConfig:
    """Convert database row to MCPServerConfig."""
    return MCPServerConfig(
        id=str(row["id"]),
        name=row["name"],
        server_type=row["server_type"],
        command=row["command"],
        url=row["url"],
        args=row["args"] or [],
        env=_parse_env(row["env"]),
        tools=row["tools"] or [],
        is_active=row["is_active"],
    )


@app.get("/api/v1/mcp-servers", response_model=List[MCPServerConfig])
async def list_mcp_servers(user: UserInfo = Depends(get_current_user)):
    """List all MCP server configurations."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM mcp_servers ORDER BY name")
        return [_row_to_mcp(row) for row in rows]


@app.post("/api/v1/mcp-servers", response_model=MCPServerConfig)
async def create_mcp_server(
    server: MCPServerCreate,
    user: UserInfo = Depends(require_admin)
):
    """Create a new MCP server configuration."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO mcp_servers (name, server_type, command, url, args, env)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *
        """, server.name, server.server_type, server.command, server.url,
            server.args, json.dumps(server.env))

        return _row_to_mcp(row)


@app.get("/api/v1/mcp-servers/sync/preview")
async def preview_gateway_config(user: UserInfo = Depends(get_current_user)):
    """Preview the Agent Gateway config that would be deployed."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM mcp_servers WHERE is_active = true ORDER BY name")
        servers = [
            {
                "name": row["name"],
                "server_type": row["server_type"],
                "command": row["command"],
                "url": row["url"],
                "args": row["args"] or [],
                "env": _parse_env(row["env"]),
            }
            for row in rows
        ]

    config_yaml = build_gateway_config(servers)
    return {
        "active_servers": len(servers),
        "config_yaml": config_yaml,
    }


@app.post("/api/v1/mcp-servers/sync")
async def sync_mcp_to_gateway(user: UserInfo = Depends(require_admin)):
    """Deploy active MCP server configs to the Agent Gateway ConfigMap and restart."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM mcp_servers WHERE is_active = true ORDER BY name")
        servers = [
            {
                "name": row["name"],
                "server_type": row["server_type"],
                "command": row["command"],
                "url": row["url"],
                "args": row["args"] or [],
                "env": _parse_env(row["env"]),
            }
            for row in rows
        ]

    cm_result = await sync_configmap(servers)
    if cm_result["status"] == "error":
        return {
            "status": "error",
            "servers_synced": len(servers),
            "configmap": cm_result,
            "restart": {"status": "skipped"},
        }

    restart_result = await restart_gateway()

    return {
        "status": "ok" if restart_result["status"] == "ok" else "partial",
        "servers_synced": len(servers),
        "configmap": cm_result,
        "restart": restart_result,
    }


@app.put("/api/v1/mcp-servers/{server_id}", response_model=MCPServerConfig)
async def update_mcp_server(
    server_id: str,
    update: MCPServerUpdate,
    user: UserInfo = Depends(require_admin)
):
    """Update an MCP server configuration."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    updates = []
    params = []
    param_idx = 1

    for field, value in update.model_dump(exclude_unset=True).items():
        if value is not None:
            if field == "env":
                updates.append(f"{field} = ${param_idx}")
                params.append(json.dumps(value))
            else:
                updates.append(f"{field} = ${param_idx}")
                params.append(value)
            param_idx += 1

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    params.append(server_id)

    async with db_pool.acquire() as conn:
        query = f"UPDATE mcp_servers SET {', '.join(updates)} WHERE id = ${param_idx} RETURNING *"
        row = await conn.fetchrow(query, *params)

        if not row:
            raise HTTPException(status_code=404, detail="MCP server not found")

        return _row_to_mcp(row)


@app.delete("/api/v1/mcp-servers/{server_id}")
async def delete_mcp_server(
    server_id: str,
    user: UserInfo = Depends(require_admin)
):
    """Delete an MCP server configuration."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with db_pool.acquire() as conn:
        result = await conn.execute("DELETE FROM mcp_servers WHERE id = $1", server_id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="MCP server not found")

    return {"status": "deleted"}


@app.post("/api/v1/mcp-servers/{server_id}/test")
async def test_mcp_server(
    server_id: str,
    user: UserInfo = Depends(get_current_user)
):
    """Test connectivity to an MCP server."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM mcp_servers WHERE id = $1", server_id)
        if not row:
            raise HTTPException(status_code=404, detail="MCP server not found")

    server_type = row["server_type"]

    if server_type == "http":
        url = row["url"]
        if not url:
            return {"status": "error", "message": "No URL configured"}
        try:
            response = await http_client.get(url, timeout=5.0)
            return {"status": "ok", "message": f"Reachable — HTTP {response.status_code}"}
        except httpx.ConnectError:
            return {"status": "error", "message": f"Cannot connect to {url}"}
        except httpx.TimeoutException:
            return {"status": "error", "message": f"Timeout connecting to {url}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    else:
        # stdio: validate config is complete (can't test binary from admin-api container)
        command = row["command"]
        if not command:
            return {"status": "error", "message": "No command configured"}
        args = row["args"] or []
        env = _parse_env(row["env"])
        parts = [command] + list(args)
        return {"status": "ok", "message": f"Config valid: {' '.join(parts)}"}


# =============================================================================
# API Key Endpoints (proxy to LiteLLM)
# =============================================================================

@app.post("/api/v1/keys/generate")
async def generate_key(
    request: KeyGenerateRequest,
    user: UserInfo = Depends(require_admin)
):
    """Generate a new API key via LiteLLM."""
    try:
        response = await http_client.post(
            f"{LITELLM_URL}/key/generate",
            json=request.model_dump(exclude_none=True),
            headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"},
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/v1/keys")
async def list_keys(user: UserInfo = Depends(get_current_user)):
    """List all API keys via LiteLLM."""
    try:
        response = await http_client.get(
            f"{LITELLM_URL}/key/list",
            headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"},
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/v1/keys/{key}")
async def get_key_info(
    key: str,
    user: UserInfo = Depends(get_current_user)
):
    """Get info about a specific API key via LiteLLM."""
    try:
        response = await http_client.get(
            f"{LITELLM_URL}/key/info",
            params={"key": key},
            headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"},
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/api/v1/keys/update")
async def update_key(
    request: KeyUpdateRequest,
    user: UserInfo = Depends(require_admin)
):
    """Update an API key via LiteLLM."""
    try:
        response = await http_client.post(
            f"{LITELLM_URL}/key/update",
            json=request.model_dump(exclude_none=True),
            headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"},
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/api/v1/keys/delete")
async def delete_keys(
    request: KeyDeleteRequest,
    user: UserInfo = Depends(require_admin)
):
    """Delete API keys via LiteLLM."""
    try:
        response = await http_client.post(
            f"{LITELLM_URL}/key/delete",
            json=request.model_dump(),
            headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"},
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# =============================================================================
# Workflow Endpoints
# =============================================================================

@app.get("/api/v1/workflows", response_model=List[WorkflowSummary])
async def list_workflows(user: UserInfo = Depends(get_current_user)):
    """List all workflow definitions."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, name, template_type, description, is_active, created_at
            FROM workflow_definitions
            ORDER BY name
        """)
        return [
            WorkflowSummary(
                id=str(row["id"]),
                name=row["name"],
                template_type=row["template_type"],
                description=row["description"],
                is_active=row["is_active"],
                created_at=row["created_at"],
            )
            for row in rows
        ]


@app.post("/api/v1/workflows", response_model=WorkflowSummary)
async def create_workflow(
    workflow: WorkflowCreate,
    user: UserInfo = Depends(require_admin)
):
    """Create a new workflow definition."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with db_pool.acquire() as conn:
        graph_def = json.dumps(workflow.config or {"template": workflow.template_type})
        row = await conn.fetchrow("""
            INSERT INTO workflow_definitions (name, template_type, description, graph_definition, is_active)
            VALUES ($1, $2, $3, $4, true)
            RETURNING *
        """, workflow.name, workflow.template_type, workflow.description, graph_def)

        return WorkflowSummary(
            id=str(row["id"]),
            name=row["name"],
            template_type=row["template_type"],
            description=row["description"],
            is_active=row["is_active"],
            created_at=row["created_at"],
        )


@app.get("/api/v1/workflow-templates")
async def list_workflow_templates(user: UserInfo = Depends(get_current_user)):
    """List available workflow templates from the Workflow Engine."""
    try:
        response = await http_client.get(
            f"{WORKFLOW_ENGINE_URL}/api/v1/templates",
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/api/v1/workflow-executions")
async def execute_workflow(
    request: WorkflowExecuteRequest,
    user: UserInfo = Depends(get_current_user)
):
    """Execute a workflow via the Workflow Engine."""
    try:
        # Translate admin-api model to workflow engine format
        payload = {
            "template": request.template_type,
            "input": {"text": request.input_text},
        }
        if request.user_id:
            payload["user_id"] = request.user_id
        if request.team_id:
            payload["team_id"] = request.team_id
        response = await http_client.post(
            f"{WORKFLOW_ENGINE_URL}/api/v1/executions",
            json=payload,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/v1/workflow-executions")
async def list_workflow_executions(user: UserInfo = Depends(get_current_user)):
    """List workflow executions from the Workflow Engine."""
    try:
        response = await http_client.get(
            f"{WORKFLOW_ENGINE_URL}/api/v1/executions",
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/v1/workflow-executions/{execution_id}")
async def get_workflow_execution(
    execution_id: str,
    user: UserInfo = Depends(get_current_user)
):
    """Get a specific workflow execution from the Workflow Engine."""
    try:
        response = await http_client.get(
            f"{WORKFLOW_ENGINE_URL}/api/v1/executions/{execution_id}",
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# =============================================================================
# Metrics Endpoints
# =============================================================================

@app.get("/api/v1/metrics/realtime", response_model=RealtimeMetrics)
async def get_realtime_metrics(user: UserInfo = Depends(get_current_user)):
    """Get real-time platform metrics."""
    # Fetch from LiteLLM and database
    model_usage = {}
    provider_status = {}

    try:
        # Get LiteLLM health
        response = await http_client.get(
            f"{LITELLM_URL}/health/liveliness",
            headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"}
        )
        provider_status["litellm"] = response.status_code == 200
    except Exception:
        provider_status["litellm"] = False

    # Get today's stats from database
    total_cost_today = 0.0
    total_tokens_today = 0
    requests_today = 0

    if db_pool:
        async with db_pool.acquire() as conn:
            # Use LiteLLM's native spend logs table
            row = await conn.fetchrow("""
                SELECT
                    COALESCE(SUM(spend), 0) as total_cost,
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COUNT(*) as request_count
                FROM "LiteLLM_SpendLogs"
                WHERE "startTime"::date = CURRENT_DATE
            """)
            if row:
                total_cost_today = float(row["total_cost"])
                total_tokens_today = int(row["total_tokens"])
                requests_today = int(row["request_count"])

            # Get model usage from LiteLLM's native table
            rows = await conn.fetch("""
                SELECT model, COUNT(*) as count
                FROM "LiteLLM_SpendLogs"
                WHERE "startTime"::date = CURRENT_DATE
                GROUP BY model
            """)
            model_usage = {row["model"]: row["count"] for row in rows}

    return RealtimeMetrics(
        timestamp=datetime.now(timezone.utc),
        requests_per_minute=requests_today // max(1, datetime.now().hour * 60 + datetime.now().minute),
        active_users=0,  # Would need session tracking
        total_cost_today=total_cost_today,
        total_tokens_today=total_tokens_today,
        average_latency_ms=0,  # Would need Prometheus
        error_rate=0.0,  # Would need Prometheus
        model_usage=model_usage,
        provider_status=provider_status,
    )


# =============================================================================
# Settings Endpoints
# =============================================================================

@app.get("/api/v1/settings", response_model=PlatformSettings)
async def get_settings(user: UserInfo = Depends(get_current_user)):
    """Get platform settings."""
    if not db_pool:
        return PlatformSettings()

    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT key, value FROM platform_settings")
        settings = PlatformSettings()

        for row in rows:
            key = row["key"]
            value = row["value"]
            if hasattr(settings, key):
                setattr(settings, key, value)

        return settings


@app.put("/api/v1/settings", response_model=PlatformSettings)
async def update_settings(
    settings: PlatformSettings,
    user: UserInfo = Depends(require_admin)
):
    """Update platform settings."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with db_pool.acquire() as conn:
        for key, value in settings.model_dump().items():
            await conn.execute("""
                INSERT INTO platform_settings (key, value, updated_at)
                VALUES ($1, $2, CURRENT_TIMESTAMP)
                ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = CURRENT_TIMESTAMP
            """, key, json.dumps(value))

    return settings


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8086)
