"""
Admin API Service

A FastAPI service providing administrative endpoints for the AI Gateway platform.

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
from typing import Optional, List
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
import httpx
import asyncpg

from auth import (
    login, LoginRequest, TokenResponse,
    get_current_user, require_admin, UserInfo
)
from models import (
    ModelConfig, ModelConfigUpdate,
    RoutingPolicy, RoutingPolicyCreate,
    Budget, BudgetCreate, BudgetUpdate,
    Team, TeamCreate, TeamUpdate, TeamMember,
    MCPServerConfig, MCPServerCreate,
    WorkflowSummary,
    RealtimeMetrics,
    PlatformSettings,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://litellm:litellm@localhost:5432/litellm")
LITELLM_URL = os.getenv("LITELLM_URL", "http://localhost:4000")
LITELLM_MASTER_KEY = os.getenv("LITELLM_MASTER_KEY", "$LITELLM_KEY")
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

# Global resources
db_pool: Optional[asyncpg.Pool] = None
http_client: Optional[httpx.AsyncClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global db_pool, http_client

    # Setup OpenTelemetry
    resource = Resource.create({"service.name": "admin-api"})
    provider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=OTEL_ENDPOINT))
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    # Create database pool
    try:
        db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
        logger.info("Database connection established")
        await _init_admin_tables()
    except Exception as e:
        logger.warning(f"Could not connect to database: {e}")

    # Create HTTP client
    http_client = httpx.AsyncClient(timeout=30.0)

    logger.info("Admin API service started")
    yield

    # Cleanup
    await http_client.aclose()
    if db_pool:
        await db_pool.close()
    logger.info("Admin API service stopped")


async def _init_admin_tables():
    """Initialize admin-specific database tables."""
    if not db_pool:
        return

    async with db_pool.acquire() as conn:
        # Model routing configuration table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS model_routing_config (
                model_id VARCHAR(255) PRIMARY KEY,
                provider VARCHAR(255),
                tier VARCHAR(50),
                cost_per_1k_input DECIMAL(20, 10),
                cost_per_1k_output DECIMAL(20, 10),
                supports_streaming BOOLEAN DEFAULT TRUE,
                supports_function_calling BOOLEAN DEFAULT FALSE,
                default_latency_sla_ms INTEGER DEFAULT 5000,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Seed default model configurations
        await conn.execute("""
            INSERT INTO model_routing_config (model_id, provider, tier, cost_per_1k_input, cost_per_1k_output, supports_streaming, supports_function_calling, default_latency_sla_ms)
            VALUES
                ('gpt-4o', 'openai', 'premium', 0.0025, 0.010, TRUE, TRUE, 5000),
                ('gpt-4o-mini', 'openai', 'budget', 0.00015, 0.0006, TRUE, TRUE, 3000),
                ('claude-3-5-sonnet', 'anthropic', 'premium', 0.003, 0.015, TRUE, TRUE, 5000),
                ('claude-3-haiku', 'anthropic', 'budget', 0.00025, 0.00125, TRUE, TRUE, 2000),
                ('grok-3', 'xai', 'premium', 0.003, 0.015, TRUE, TRUE, 4000),
                ('llama-3.1-70b', 'vllm', 'standard', 0.0001, 0.0003, TRUE, FALSE, 8000)
            ON CONFLICT DO NOTHING
        """)

        # Cost tracking daily table (for FinOps metrics)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS cost_tracking_daily (
                id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                date DATE NOT NULL,
                user_id VARCHAR(255),
                team_id VARCHAR(255),
                model VARCHAR(255) NOT NULL,
                provider VARCHAR(255),
                request_count BIGINT DEFAULT 0,
                input_tokens BIGINT DEFAULT 0,
                output_tokens BIGINT DEFAULT 0,
                total_cost DECIMAL(20, 10) DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date, user_id, team_id, model)
            )
        """)

        # Routing policies table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS routing_policies (
                id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL,
                description TEXT,
                priority INTEGER DEFAULT 0,
                condition TEXT NOT NULL,
                action VARCHAR(50) DEFAULT 'permit',
                target_models VARCHAR(255)[],
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Budgets table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                entity_type VARCHAR(50) NOT NULL,
                entity_id VARCHAR(255),
                monthly_limit DECIMAL(20, 10) NOT NULL,
                current_spend DECIMAL(20, 10) DEFAULT 0,
                soft_limit_percent DECIMAL(5, 2) DEFAULT 0.80,
                hard_limit_percent DECIMAL(5, 2) DEFAULT 1.00,
                alert_email VARCHAR(255),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(entity_type, entity_id)
            )
        """)

        # Teams table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL,
                description TEXT,
                monthly_budget DECIMAL(20, 10),
                default_model VARCHAR(255),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Team members table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS team_members (
                team_id UUID REFERENCES teams(id) ON DELETE CASCADE,
                user_id VARCHAR(255) NOT NULL,
                role VARCHAR(50) DEFAULT 'member',
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (team_id, user_id)
            )
        """)

        # MCP servers table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS mcp_servers (
                id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL,
                server_type VARCHAR(50) NOT NULL,
                command TEXT,
                url TEXT,
                args TEXT[],
                env JSONB,
                tools TEXT[],
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Platform settings table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS platform_settings (
                key VARCHAR(255) PRIMARY KEY,
                value JSONB NOT NULL,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Seed default platform settings
        await conn.execute("""
            INSERT INTO platform_settings (key, value)
            VALUES
                ('default_model', '"gpt-4o-mini"'),
                ('global_rate_limit', '1000'),
                ('enable_caching', 'true'),
                ('cache_ttl_seconds', '3600'),
                ('enable_cost_tracking', 'true'),
                ('enable_budget_enforcement', 'true'),
                ('enable_routing_policies', 'true'),
                ('maintenance_mode', 'false')
            ON CONFLICT DO NOTHING
        """)

        # Workflow definitions table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS workflow_definitions (
                id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL,
                version VARCHAR(50) DEFAULT '1.0.0',
                template_type VARCHAR(100),
                description TEXT,
                graph_definition JSONB NOT NULL,
                input_schema JSONB,
                output_schema JSONB,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Seed sample budgets
        await conn.execute("""
            INSERT INTO budgets (name, entity_type, entity_id, monthly_limit, soft_limit_percent, hard_limit_percent)
            VALUES
                ('Engineering Budget', 'team', 'engineering', 500.00, 0.80, 1.00),
                ('Data Science Budget', 'team', 'data-science', 1000.00, 0.80, 1.00),
                ('Global Budget', 'global', NULL, 5000.00, 0.80, 0.95)
            ON CONFLICT DO NOTHING
        """)

        # Seed sample teams
        await conn.execute("""
            INSERT INTO teams (name, description, monthly_budget, default_model)
            VALUES
                ('engineering', 'Engineering team', 500.00, 'gpt-4o-mini'),
                ('data-science', 'Data Science team', 1000.00, 'gpt-4o'),
                ('product', 'Product team', 250.00, 'claude-3-haiku')
            ON CONFLICT DO NOTHING
        """)

        logger.info("Admin tables initialized")


app = FastAPI(
    title="AI Gateway Admin API",
    description="Administrative API for managing the AI Gateway platform",
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

@app.get("/api/v1/mcp-servers", response_model=List[MCPServerConfig])
async def list_mcp_servers(user: UserInfo = Depends(get_current_user)):
    """List all MCP server configurations."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM mcp_servers ORDER BY name")
        return [
            MCPServerConfig(
                id=str(row["id"]),
                name=row["name"],
                server_type=row["server_type"],
                command=row["command"],
                url=row["url"],
                args=row["args"] or [],
                env=row["env"] or {},
                tools=row["tools"] or [],
                is_active=row["is_active"],
            )
            for row in rows
        ]


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

        return MCPServerConfig(
            id=str(row["id"]),
            name=row["name"],
            server_type=row["server_type"],
            command=row["command"],
            url=row["url"],
            args=row["args"] or [],
            env=row["env"] or {},
            tools=row["tools"] or [],
            is_active=row["is_active"],
        )


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
