"""
Cedar Policy-Driven Model Routing Service

A FastAPI service that uses Cedar policies to intelligently select
the optimal model for LLM requests based on cost, latency, budget,
and capability constraints.

Features:
- Cedar policy evaluation for routing decisions
- Real-time Prometheus metrics integration
- Intelligent model ranking and fallback selection
- Budget-aware routing
- Latency SLA enforcement
"""

import os
import logging
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from decimal import Decimal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
import httpx
import asyncpg
import redis.asyncio as redis

from models import (
    RoutingRequest, RoutingDecision, ModelInfo, ModelTier,
    PolicyEvaluationRequest, PolicyEvaluationResponse,
    RoutingDecisionRecord, ModelRoutingConfig
)
from cedar_engine import CedarEngine
from metrics_collector import MetricsCollector
from routing_strategy import RoutingStrategy

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Global resources
http_client: Optional[httpx.AsyncClient] = None
db_pool: Optional[asyncpg.Pool] = None
redis_client: Optional[redis.Redis] = None
cedar_engine: Optional[CedarEngine] = None
metrics_collector: Optional[MetricsCollector] = None
routing_strategy: Optional[RoutingStrategy] = None


# Default model configurations
DEFAULT_MODELS: List[Dict[str, Any]] = [
    {
        "model_id": "gpt-4o",
        "provider": "openai",
        "tier": "premium",
        "cost_per_1k_input": Decimal("0.0025"),
        "cost_per_1k_output": Decimal("0.010"),
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": True,
        "default_latency_sla_ms": 5000
    },
    {
        "model_id": "gpt-4o-mini",
        "provider": "openai",
        "tier": "budget",
        "cost_per_1k_input": Decimal("0.00015"),
        "cost_per_1k_output": Decimal("0.0006"),
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": True,
        "default_latency_sla_ms": 3000
    },
    {
        "model_id": "claude-3-5-sonnet",
        "provider": "anthropic",
        "tier": "premium",
        "cost_per_1k_input": Decimal("0.003"),
        "cost_per_1k_output": Decimal("0.015"),
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": True,
        "default_latency_sla_ms": 5000
    },
    {
        "model_id": "claude-3-haiku",
        "provider": "anthropic",
        "tier": "budget",
        "cost_per_1k_input": Decimal("0.00025"),
        "cost_per_1k_output": Decimal("0.00125"),
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": True,
        "default_latency_sla_ms": 2000
    },
    {
        "model_id": "grok-3",
        "provider": "xai",
        "tier": "premium",
        "cost_per_1k_input": Decimal("0.003"),
        "cost_per_1k_output": Decimal("0.015"),
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": False,
        "default_latency_sla_ms": 4000
    },
    {
        "model_id": "llama-3.1-70b",
        "provider": "vllm",
        "tier": "standard",
        "cost_per_1k_input": Decimal("0.0001"),
        "cost_per_1k_output": Decimal("0.0003"),
        "supports_streaming": True,
        "supports_function_calling": False,
        "supports_vision": False,
        "default_latency_sla_ms": 8000
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global http_client, db_pool, redis_client, cedar_engine, metrics_collector, routing_strategy

    # Setup OpenTelemetry
    otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    resource = Resource.create({"service.name": "policy-router"})
    provider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=otel_endpoint))
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    # Create HTTP client
    http_client = httpx.AsyncClient(timeout=30.0)

    # Create database pool
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        try:
            db_pool = await asyncpg.create_pool(database_url, min_size=2, max_size=10)
            logger.info("Database connection established")
            await _init_database_tables()
        except Exception as e:
            logger.warning(f"Could not connect to database: {e}")

    # Create Redis client
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    try:
        redis_client = redis.from_url(redis_url, decode_responses=True)
        await redis_client.ping()
        logger.info("Redis connection established")
    except Exception as e:
        logger.warning(f"Could not connect to Redis: {e}")
        redis_client = None

    # Initialize Cedar engine
    policies_path = os.getenv("CEDAR_POLICIES_PATH", "/etc/cedar/policies")
    cedar_engine = CedarEngine(policies_path)

    # Initialize metrics collector
    prometheus_url = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
    metrics_collector = MetricsCollector(prometheus_url)

    # Initialize routing strategy
    routing_strategy = RoutingStrategy()

    logger.info("Policy router service started")
    yield

    # Cleanup
    await http_client.aclose()
    if db_pool:
        await db_pool.close()
    if redis_client:
        await redis_client.close()
    if metrics_collector:
        await metrics_collector.close()

    logger.info("Policy router service stopped")


async def _init_database_tables():
    """Initialize database tables if they don't exist."""
    if not db_pool:
        return

    try:
        async with db_pool.acquire() as conn:
            # Create routing_decisions table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS routing_decisions (
                    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    user_id VARCHAR(255),
                    team_id VARCHAR(255),
                    requested_model VARCHAR(255),
                    selected_model VARCHAR(255) NOT NULL,
                    fallback_models VARCHAR(255)[],
                    decision_reason TEXT,
                    context_snapshot JSONB
                )
            """)

            # Create model_routing_config table
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

            # Create indexes
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_routing_decisions_timestamp
                ON routing_decisions(timestamp)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_routing_decisions_user
                ON routing_decisions(user_id)
            """)

            logger.info("Database tables initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}")


app = FastAPI(
    title="Cedar Policy-Driven Model Router",
    description="Intelligent model routing using Cedar policies",
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

tracer = trace.get_tracer(__name__)


async def _get_available_models() -> List[ModelInfo]:
    """Get all available models with current metrics."""
    models = []

    # Try loading from database first
    if db_pool:
        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM model_routing_config")
                if rows:
                    for row in rows:
                        models.append(ModelInfo(
                            model_id=row["model_id"],
                            provider=row["provider"],
                            tier=ModelTier(row["tier"]),
                            cost_per_1k_input=row["cost_per_1k_input"],
                            cost_per_1k_output=row["cost_per_1k_output"],
                            supports_streaming=row["supports_streaming"],
                            supports_function_calling=row["supports_function_calling"],
                            default_latency_sla_ms=row["default_latency_sla_ms"],
                        ))
        except Exception as e:
            logger.warning(f"Could not load models from database: {e}")

    # Fall back to default models if none loaded
    if not models:
        for m in DEFAULT_MODELS:
            models.append(ModelInfo(
                model_id=m["model_id"],
                provider=m["provider"],
                tier=ModelTier(m["tier"]),
                cost_per_1k_input=m["cost_per_1k_input"],
                cost_per_1k_output=m["cost_per_1k_output"],
                supports_streaming=m["supports_streaming"],
                supports_function_calling=m["supports_function_calling"],
                supports_vision=m.get("supports_vision", False),
                default_latency_sla_ms=m["default_latency_sla_ms"],
            ))

    # Fetch current metrics
    if metrics_collector:
        model_ids = [m.model_id for m in models]
        metrics = await metrics_collector.get_all_model_metrics(model_ids)

        for model in models:
            if model.model_id in metrics:
                m = metrics[model.model_id]
                model.current_latency_ms = m.get("latency_p95_ms")
                model.current_error_rate = m.get("error_rate")
                model.requests_per_minute = m.get("rpm")
                model.is_available = m.get("is_available", True)

    return models


async def _record_decision(decision: RoutingDecisionRecord):
    """Record routing decision to database."""
    if not db_pool:
        return

    try:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO routing_decisions
                (user_id, team_id, requested_model, selected_model, fallback_models, decision_reason, context_snapshot)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
                decision.user_id,
                decision.team_id,
                decision.requested_model,
                decision.selected_model,
                decision.fallback_models,
                decision.decision_reason,
                json.dumps(decision.context_snapshot)
            )
    except Exception as e:
        logger.error(f"Failed to record routing decision: {e}")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/route", response_model=RoutingDecision)
async def route_request(request: RoutingRequest):
    """
    Evaluate policies and select optimal model for a request.

    This endpoint:
    1. Loads available models with current metrics
    2. Evaluates Cedar policies for each model
    3. Ranks models based on cost, latency, budget
    4. Returns selected model with fallbacks
    """
    with tracer.start_as_current_span("route_request") as span:
        span.set_attribute("user_id", request.user_id or "")
        span.set_attribute("requested_model", request.requested_model or "")

        # Get available models
        models = await _get_available_models()
        span.set_attribute("available_models", len(models))

        if not models:
            raise HTTPException(status_code=503, detail="No models available")

        # Build request context
        context = {
            "cost_budget_remaining": request.budget_remaining,
            "latency_sla_ms": request.latency_sla_ms,
            "required_capabilities": request.required_capabilities or [],
            "priority": request.priority,
        }

        # Evaluate Cedar policies for each model
        policy_results = {}
        if cedar_engine:
            for model in models:
                model_attrs = {
                    "provider": model.provider,
                    "tier": model.tier.value,
                    "current_latency_ms": model.current_latency_ms,
                    "current_error_rate": model.current_error_rate,
                }
                allowed, reasons = cedar_engine.evaluate_model_selection(
                    user_id=request.user_id,
                    team_id=request.team_id,
                    model_id=model.model_id,
                    model_attrs=model_attrs,
                    request_context=context
                )
                policy_results[model.model_id] = (allowed, reasons)

        # Filter by requested model alias if specified
        if request.requested_model:
            resolved = routing_strategy.resolve_model_alias(request.requested_model, models)
            if resolved:
                # Put the requested model first if it passes policies
                if resolved in policy_results and policy_results[resolved][0]:
                    context["preferred_model"] = resolved

        # Select model with routing strategy
        selected, fallbacks, reason = routing_strategy.select_with_fallbacks(
            models=models,
            request=request,
            policy_results=policy_results
        )

        if not selected:
            raise HTTPException(
                status_code=503,
                detail="No suitable models available for the given constraints"
            )

        # Estimate cost if messages provided
        estimated_cost = None
        if request.messages:
            # Rough token estimation: 4 chars per token
            input_tokens = sum(len(str(m)) // 4 for m in request.messages)
            output_tokens = request.max_tokens or 1000
            estimated_cost = routing_strategy.estimate_cost(selected, input_tokens, output_tokens)

        # Record decision
        record = RoutingDecisionRecord(
            timestamp=datetime.now(timezone.utc),
            user_id=request.user_id,
            team_id=request.team_id,
            requested_model=request.requested_model,
            selected_model=selected.model_id,
            fallback_models=[m.model_id for m in fallbacks],
            decision_reason=reason,
            context_snapshot=context
        )
        await _record_decision(record)

        span.set_attribute("selected_model", selected.model_id)
        span.set_attribute("fallback_count", len(fallbacks))

        return RoutingDecision(
            selected_model=selected.model_id,
            fallback_models=[m.model_id for m in fallbacks],
            decision_reason=reason,
            estimated_cost=estimated_cost,
            estimated_latency_ms=int(selected.current_latency_ms) if selected.current_latency_ms else None
        )


@app.post("/evaluate", response_model=PolicyEvaluationResponse)
async def evaluate_policy(request: PolicyEvaluationRequest):
    """
    Direct Cedar policy evaluation for debugging.

    Use this endpoint to test policy evaluation directly
    without the full routing logic.
    """
    if not cedar_engine:
        raise HTTPException(status_code=503, detail="Cedar engine not available")

    return cedar_engine.evaluate(
        principal=request.principal,
        action=request.action,
        resource=request.resource,
        context=request.context
    )


@app.post("/policies/reload")
async def reload_policies():
    """Hot-reload Cedar policies from disk."""
    if not cedar_engine:
        raise HTTPException(status_code=503, detail="Cedar engine not available")

    count = cedar_engine.reload_policies()
    return {"status": "ok", "policies_loaded": count}


@app.get("/models")
async def list_models(include_metrics: bool = Query(default=True)):
    """
    List all available models with current metrics.

    Args:
        include_metrics: Whether to include real-time metrics
    """
    models = await _get_available_models()

    return {
        "models": [
            {
                "model_id": m.model_id,
                "provider": m.provider,
                "tier": m.tier.value,
                "cost_per_1k_input": str(m.cost_per_1k_input),
                "cost_per_1k_output": str(m.cost_per_1k_output),
                "supports_streaming": m.supports_streaming,
                "supports_function_calling": m.supports_function_calling,
                "supports_vision": m.supports_vision,
                "default_latency_sla_ms": m.default_latency_sla_ms,
                "current_latency_ms": m.current_latency_ms if include_metrics else None,
                "current_error_rate": m.current_error_rate if include_metrics else None,
                "requests_per_minute": m.requests_per_minute if include_metrics else None,
                "is_available": m.is_available if include_metrics else None,
            }
            for m in models
        ]
    }


@app.get("/decisions")
async def get_recent_decisions(
    user_id: Optional[str] = None,
    team_id: Optional[str] = None,
    limit: int = Query(default=100, le=1000)
):
    """Get recent routing decisions."""
    if not db_pool:
        return {"decisions": [], "message": "Database not available"}

    try:
        async with db_pool.acquire() as conn:
            query = "SELECT * FROM routing_decisions WHERE 1=1"
            params = []
            param_idx = 1

            if user_id:
                query += f" AND user_id = ${param_idx}"
                params.append(user_id)
                param_idx += 1

            if team_id:
                query += f" AND team_id = ${param_idx}"
                params.append(team_id)
                param_idx += 1

            query += f" ORDER BY timestamp DESC LIMIT ${param_idx}"
            params.append(limit)

            rows = await conn.fetch(query, *params)

            return {
                "decisions": [
                    {
                        "id": str(row["id"]),
                        "timestamp": row["timestamp"].isoformat(),
                        "user_id": row["user_id"],
                        "team_id": row["team_id"],
                        "requested_model": row["requested_model"],
                        "selected_model": row["selected_model"],
                        "fallback_models": row["fallback_models"],
                        "decision_reason": row["decision_reason"],
                    }
                    for row in rows
                ]
            }
    except Exception as e:
        logger.error(f"Failed to get decisions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8084)
