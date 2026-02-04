"""
Budget Enforcement Webhook

A FastAPI service that acts as a webhook for LiteLLM to enforce budget limits.
This service is called before each request to validate budget constraints.

Features:
- Pre-request budget validation
- Soft/hard budget limit enforcement
- Budget alerts and notifications
- Integration with cost predictor
"""

import os
import logging
from typing import Optional
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from decimal import Decimal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
import httpx
import asyncpg

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WebhookRequest(BaseModel):
    """LiteLLM webhook request format."""
    data: dict = Field(..., description="Request data from LiteLLM")


class WebhookResponse(BaseModel):
    """Webhook response format."""
    allow: bool = Field(..., description="Whether to allow the request")
    message: Optional[str] = Field(default=None, description="Message for rejection or warning")
    modified_data: Optional[dict] = Field(default=None, description="Modified request data")


class BudgetAlert(BaseModel):
    """Budget alert model."""
    user_id: Optional[str] = None
    team_id: Optional[str] = None
    alert_type: str
    threshold_percent: float
    current_spend: float
    budget_limit: float
    message: str


# Global resources
http_client: Optional[httpx.AsyncClient] = None
db_pool: Optional[asyncpg.Pool] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global http_client, db_pool

    # Setup OpenTelemetry
    otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    resource = Resource.create({"service.name": "budget-webhook"})
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
        except Exception as e:
            logger.warning(f"Could not connect to database: {e}")

    logger.info("Budget webhook service started")
    yield

    # Cleanup
    await http_client.aclose()
    if db_pool:
        await db_pool.close()
    logger.info("Budget webhook service stopped")


app = FastAPI(
    title="Budget Enforcement Webhook",
    description="Webhook service for LiteLLM budget enforcement",
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

# Budget thresholds
SOFT_LIMIT_THRESHOLD = float(os.getenv("SOFT_LIMIT_THRESHOLD", "0.8"))  # 80%
HARD_LIMIT_THRESHOLD = float(os.getenv("HARD_LIMIT_THRESHOLD", "1.0"))  # 100%


async def get_budget_info(api_key: str) -> dict:
    """Get budget information from LiteLLM."""
    litellm_url = os.getenv("LITELLM_URL", "http://localhost:4000")
    litellm_master_key = os.getenv("LITELLM_MASTER_KEY", "")

    try:
        response = await http_client.get(
            f"{litellm_url}/key/info",
            params={"key": api_key},
            headers={"Authorization": f"Bearer {litellm_master_key}"}
        )

        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"Failed to get key info: {response.status_code}")
            return {}
    except Exception as e:
        logger.error(f"Error getting budget info: {e}")
        return {}


async def predict_cost(model: str, messages: list, max_tokens: Optional[int]) -> float:
    """Get cost prediction from cost predictor service."""
    predictor_url = os.getenv("COST_PREDICTOR_URL", "http://localhost:8080")

    try:
        response = await http_client.post(
            f"{predictor_url}/predict",
            json={
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens
            }
        )

        if response.status_code == 200:
            return response.json().get("total_estimated_cost_usd", 0)
        else:
            logger.warning(f"Cost prediction failed: {response.status_code}")
            return 0
    except Exception as e:
        logger.error(f"Error predicting cost: {e}")
        return 0


async def record_alert(alert: BudgetAlert):
    """Record budget alert to database."""
    if not db_pool:
        logger.warning("No database connection, alert not recorded")
        return

    try:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO budget_alerts
                (user_id, team_id, alert_type, threshold_percent, current_spend, budget_limit, message)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """, alert.user_id, alert.team_id, alert.alert_type,
                alert.threshold_percent, alert.current_spend, alert.budget_limit, alert.message)
    except Exception as e:
        logger.error(f"Failed to record alert: {e}")


async def send_notification(alert: BudgetAlert):
    """Send budget alert notification (webhook, email, Slack, etc.)."""
    webhook_url = os.getenv("ALERT_WEBHOOK_URL")

    if not webhook_url:
        logger.info(f"Alert (no webhook configured): {alert.message}")
        return

    try:
        await http_client.post(
            webhook_url,
            json={
                "type": alert.alert_type,
                "user_id": alert.user_id,
                "team_id": alert.team_id,
                "threshold": alert.threshold_percent,
                "current_spend": alert.current_spend,
                "budget_limit": alert.budget_limit,
                "message": alert.message,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/webhook/pre-request", response_model=WebhookResponse)
async def pre_request_webhook(request: WebhookRequest):
    """
    Pre-request webhook called by LiteLLM before processing a request.

    This validates:
    1. Budget hasn't been exceeded
    2. Estimated cost won't exceed remaining budget
    3. Soft limit warnings are triggered
    """
    with tracer.start_as_current_span("pre_request_check") as span:
        data = request.data

        # Extract request details
        api_key = data.get("api_key", "")
        model = data.get("model", "")
        messages = data.get("messages", [])
        max_tokens = data.get("max_tokens")
        user_id = data.get("user", "")
        team_id = data.get("team_id", "")

        span.set_attribute("model", model)
        span.set_attribute("user_id", user_id)

        # Get budget info
        budget_info = await get_budget_info(api_key)

        if not budget_info:
            # Allow if we can't check budget
            return WebhookResponse(allow=True, message="Budget check unavailable")

        max_budget = budget_info.get("max_budget")
        current_spend = budget_info.get("spend", 0)

        if max_budget is None:
            # No budget limit set
            return WebhookResponse(allow=True)

        span.set_attribute("max_budget", max_budget)
        span.set_attribute("current_spend", current_spend)

        # Calculate usage percentage
        usage_percent = current_spend / max_budget if max_budget > 0 else 0
        remaining_budget = max_budget - current_spend

        # Predict cost of this request
        estimated_cost = await predict_cost(model, messages, max_tokens)
        span.set_attribute("estimated_cost", estimated_cost)

        # Check hard limit
        if usage_percent >= HARD_LIMIT_THRESHOLD:
            alert = BudgetAlert(
                user_id=user_id,
                team_id=team_id,
                alert_type="budget_exceeded",
                threshold_percent=usage_percent * 100,
                current_spend=current_spend,
                budget_limit=max_budget,
                message=f"Budget limit exceeded: ${current_spend:.2f} / ${max_budget:.2f}"
            )
            await record_alert(alert)
            await send_notification(alert)

            return WebhookResponse(
                allow=False,
                message=f"Budget limit exceeded. Current spend: ${current_spend:.2f}, Limit: ${max_budget:.2f}"
            )

        # Check if this request would exceed budget
        if estimated_cost > remaining_budget:
            alert = BudgetAlert(
                user_id=user_id,
                team_id=team_id,
                alert_type="request_exceeds_budget",
                threshold_percent=usage_percent * 100,
                current_spend=current_spend,
                budget_limit=max_budget,
                message=f"Request would exceed budget: estimated ${estimated_cost:.4f}, remaining ${remaining_budget:.2f}"
            )
            await record_alert(alert)

            return WebhookResponse(
                allow=False,
                message=f"Request would exceed budget. Estimated cost: ${estimated_cost:.4f}, Remaining: ${remaining_budget:.2f}"
            )

        # Check soft limit (warning)
        if usage_percent >= SOFT_LIMIT_THRESHOLD:
            alert = BudgetAlert(
                user_id=user_id,
                team_id=team_id,
                alert_type="approaching_limit",
                threshold_percent=usage_percent * 100,
                current_spend=current_spend,
                budget_limit=max_budget,
                message=f"Approaching budget limit: {usage_percent*100:.1f}% used"
            )
            await record_alert(alert)
            await send_notification(alert)

            return WebhookResponse(
                allow=True,
                message=f"Warning: Approaching budget limit ({usage_percent*100:.1f}% used)"
            )

        return WebhookResponse(allow=True)


@app.post("/webhook/post-request")
async def post_request_webhook(request: WebhookRequest):
    """
    Post-request webhook called by LiteLLM after processing a request.

    This records actual costs and updates tracking.
    """
    with tracer.start_as_current_span("post_request_record") as span:
        data = request.data

        user_id = data.get("user", "")
        team_id = data.get("team_id", "")
        model = data.get("model", "")
        usage = data.get("usage", {})
        cost = data.get("cost", 0)

        span.set_attribute("model", model)
        span.set_attribute("user_id", user_id)
        span.set_attribute("cost", cost)
        span.set_attribute("input_tokens", usage.get("prompt_tokens", 0))
        span.set_attribute("output_tokens", usage.get("completion_tokens", 0))

        # Record to database for FinOps reporting
        if db_pool:
            try:
                async with db_pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO cost_tracking_daily
                        (date, user_id, team_id, model, request_count, input_tokens, output_tokens, total_cost)
                        VALUES (CURRENT_DATE, $1, $2, $3, 1, $4, $5, $6)
                        ON CONFLICT (date, user_id, team_id, model)
                        DO UPDATE SET
                            request_count = cost_tracking_daily.request_count + 1,
                            input_tokens = cost_tracking_daily.input_tokens + $4,
                            output_tokens = cost_tracking_daily.output_tokens + $5,
                            total_cost = cost_tracking_daily.total_cost + $6,
                            updated_at = CURRENT_TIMESTAMP
                    """, user_id, team_id, model,
                        usage.get("prompt_tokens", 0),
                        usage.get("completion_tokens", 0),
                        Decimal(str(cost)))
            except Exception as e:
                logger.error(f"Failed to record cost: {e}")

        return {"status": "recorded"}


@app.get("/alerts")
async def get_recent_alerts(
    user_id: Optional[str] = None,
    team_id: Optional[str] = None,
    limit: int = 100
):
    """Get recent budget alerts."""
    if not db_pool:
        return {"alerts": [], "message": "Database not available"}

    try:
        async with db_pool.acquire() as conn:
            query = "SELECT * FROM budget_alerts WHERE 1=1"
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

            query += f" ORDER BY created_at DESC LIMIT ${param_idx}"
            params.append(limit)

            rows = await conn.fetch(query, *params)

            return {
                "alerts": [dict(row) for row in rows]
            }
    except Exception as e:
        logger.error(f"Failed to get alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
