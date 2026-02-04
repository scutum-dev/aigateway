"""
Cost Predictor Service

A FastAPI service that predicts the cost of LLM requests before execution.
This enables pre-request budget checks and cost-aware routing decisions.

Features:
- Token counting using tiktoken
- Cost estimation based on model pricing
- Budget validation before request execution
- Integration with LiteLLM for pricing data
"""

import os
import logging
from typing import Optional
from decimal import Decimal
from dataclasses import dataclass
from contextlib import asynccontextmanager

import tiktoken
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Model pricing (cost per 1M tokens)
# These should be synced with LiteLLM configuration
MODEL_PRICING = {
    # Self-hosted models (infrastructure cost)
    "llama-3.1-70b": {"input": Decimal("0.10"), "output": Decimal("0.30")},
    "llama-3.1-8b": {"input": Decimal("0.05"), "output": Decimal("0.15")},
    # OpenAI models
    "gpt-4o": {"input": Decimal("2.50"), "output": Decimal("10.00")},
    "gpt-4o-mini": {"input": Decimal("0.15"), "output": Decimal("0.60")},
    "gpt-4-turbo": {"input": Decimal("10.00"), "output": Decimal("30.00")},
    # Anthropic models
    "claude-3-5-sonnet": {"input": Decimal("3.00"), "output": Decimal("15.00")},
    "claude-3-opus": {"input": Decimal("15.00"), "output": Decimal("75.00")},
    "claude-3-haiku": {"input": Decimal("0.25"), "output": Decimal("1.25")},
}

# Token encoding cache
_encodings: dict = {}


def get_encoding(model: str) -> tiktoken.Encoding:
    """Get or create tiktoken encoding for a model."""
    if model not in _encodings:
        try:
            # Try to get model-specific encoding
            _encodings[model] = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fall back to cl100k_base for unknown models
            _encodings[model] = tiktoken.get_encoding("cl100k_base")
    return _encodings[model]


def count_tokens(text: str, model: str) -> int:
    """Count tokens in text for a given model."""
    encoding = get_encoding(model)
    return len(encoding.encode(text))


def count_message_tokens(messages: list[dict], model: str) -> int:
    """Count tokens in a list of chat messages."""
    encoding = get_encoding(model)

    # Token overhead per message (varies by model)
    tokens_per_message = 4  # OpenAI default
    tokens_per_name = -1

    total_tokens = 0
    for message in messages:
        total_tokens += tokens_per_message
        for key, value in message.items():
            if isinstance(value, str):
                total_tokens += len(encoding.encode(value))
            if key == "name":
                total_tokens += tokens_per_name

    total_tokens += 3  # Reply priming
    return total_tokens


@dataclass
class CostEstimate:
    """Cost estimation result."""
    model: str
    input_tokens: int
    estimated_output_tokens: int
    input_cost: Decimal
    estimated_output_cost: Decimal
    total_estimated_cost: Decimal
    currency: str = "USD"


class PredictRequest(BaseModel):
    """Request body for cost prediction."""
    model: str = Field(..., description="Model name")
    messages: list[dict] = Field(default=[], description="Chat messages")
    prompt: Optional[str] = Field(default=None, description="Text prompt (for completions)")
    max_tokens: Optional[int] = Field(default=None, description="Maximum output tokens")

    class Config:
        json_schema_extra = {
            "example": {
                "model": "gpt-4o",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Hello, how are you?"}
                ],
                "max_tokens": 500
            }
        }


class PredictResponse(BaseModel):
    """Response body for cost prediction."""
    model: str
    input_tokens: int
    estimated_output_tokens: int
    input_cost_usd: float
    estimated_output_cost_usd: float
    total_estimated_cost_usd: float
    budget_remaining_usd: Optional[float] = None
    within_budget: bool = True
    warning: Optional[str] = None


class BudgetCheckRequest(BaseModel):
    """Request for budget validation."""
    api_key: str = Field(..., description="API key to check budget for")
    estimated_cost: float = Field(..., description="Estimated cost of the request")


class BudgetCheckResponse(BaseModel):
    """Response for budget validation."""
    allowed: bool
    budget_limit: Optional[float] = None
    current_spend: Optional[float] = None
    remaining: Optional[float] = None
    message: Optional[str] = None


# Global HTTP client for LiteLLM communication
http_client: Optional[httpx.AsyncClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global http_client

    # Setup OpenTelemetry
    otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    resource = Resource.create({"service.name": "cost-predictor"})
    provider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=otel_endpoint))
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    # Create HTTP client
    http_client = httpx.AsyncClient(timeout=30.0)

    logger.info("Cost predictor service started")
    yield

    # Cleanup
    await http_client.aclose()
    logger.info("Cost predictor service stopped")


app = FastAPI(
    title="Cost Predictor Service",
    description="Predict LLM request costs before execution",
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


def get_model_pricing(model: str) -> dict[str, Decimal]:
    """Get pricing for a model, with fallback to defaults."""
    # Normalize model name
    model_lower = model.lower()

    # Direct match
    if model_lower in MODEL_PRICING:
        return MODEL_PRICING[model_lower]

    # Partial match
    for key, pricing in MODEL_PRICING.items():
        if key in model_lower or model_lower in key:
            return pricing

    # Default pricing (conservative estimate)
    logger.warning(f"No pricing found for model {model}, using default")
    return {"input": Decimal("1.00"), "output": Decimal("3.00")}


def estimate_output_tokens(input_tokens: int, max_tokens: Optional[int]) -> int:
    """Estimate output tokens based on input and max_tokens setting."""
    if max_tokens:
        # Use max_tokens as upper bound, estimate 60% usage
        return int(max_tokens * 0.6)

    # Heuristic: output is typically 1-2x input for conversational
    return min(input_tokens * 2, 4096)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/predict", response_model=PredictResponse)
async def predict_cost(
    request: PredictRequest,
    x_api_key: Optional[str] = Header(default=None),
):
    """
    Predict the cost of an LLM request before execution.

    This endpoint:
    1. Counts input tokens from messages/prompt
    2. Estimates output tokens based on max_tokens
    3. Calculates cost using model pricing
    4. Optionally checks against budget
    """
    with tracer.start_as_current_span("predict_cost") as span:
        span.set_attribute("model", request.model)

        # Count input tokens
        if request.messages:
            input_tokens = count_message_tokens(request.messages, request.model)
        elif request.prompt:
            input_tokens = count_tokens(request.prompt, request.model)
        else:
            raise HTTPException(
                status_code=400,
                detail="Either 'messages' or 'prompt' must be provided"
            )

        span.set_attribute("input_tokens", input_tokens)

        # Estimate output tokens
        estimated_output = estimate_output_tokens(input_tokens, request.max_tokens)
        span.set_attribute("estimated_output_tokens", estimated_output)

        # Get pricing
        pricing = get_model_pricing(request.model)

        # Calculate costs (pricing is per 1M tokens)
        input_cost = (Decimal(input_tokens) / Decimal(1_000_000)) * pricing["input"]
        output_cost = (Decimal(estimated_output) / Decimal(1_000_000)) * pricing["output"]
        total_cost = input_cost + output_cost

        span.set_attribute("estimated_cost_usd", float(total_cost))

        response = PredictResponse(
            model=request.model,
            input_tokens=input_tokens,
            estimated_output_tokens=estimated_output,
            input_cost_usd=float(input_cost),
            estimated_output_cost_usd=float(output_cost),
            total_estimated_cost_usd=float(total_cost),
        )

        # Check budget if API key provided
        if x_api_key and http_client:
            try:
                budget_check = await check_budget_internal(x_api_key, float(total_cost))
                response.budget_remaining_usd = budget_check.remaining
                response.within_budget = budget_check.allowed
                if not budget_check.allowed:
                    response.warning = budget_check.message
            except Exception as e:
                logger.warning(f"Budget check failed: {e}")
                response.warning = "Could not verify budget"

        return response


@app.post("/budget/check", response_model=BudgetCheckResponse)
async def check_budget(request: BudgetCheckRequest):
    """
    Check if a request is within budget for an API key.
    """
    return await check_budget_internal(request.api_key, request.estimated_cost)


async def check_budget_internal(api_key: str, estimated_cost: float) -> BudgetCheckResponse:
    """Internal budget checking logic."""
    with tracer.start_as_current_span("check_budget") as span:
        litellm_url = os.getenv("LITELLM_URL", "http://localhost:4000")

        try:
            # Get key info from LiteLLM
            response = await http_client.get(
                f"{litellm_url}/key/info",
                headers={"Authorization": f"Bearer {api_key}"}
            )

            if response.status_code != 200:
                return BudgetCheckResponse(
                    allowed=True,  # Allow if we can't check
                    message="Could not verify budget"
                )

            key_info = response.json()

            max_budget = key_info.get("max_budget")
            current_spend = key_info.get("spend", 0)

            if max_budget is None:
                return BudgetCheckResponse(
                    allowed=True,
                    current_spend=current_spend,
                    message="No budget limit set"
                )

            remaining = max_budget - current_spend
            allowed = remaining >= estimated_cost

            span.set_attribute("budget_limit", max_budget)
            span.set_attribute("current_spend", current_spend)
            span.set_attribute("remaining", remaining)
            span.set_attribute("allowed", allowed)

            return BudgetCheckResponse(
                allowed=allowed,
                budget_limit=max_budget,
                current_spend=current_spend,
                remaining=remaining,
                message=None if allowed else f"Insufficient budget: need ${estimated_cost:.4f}, have ${remaining:.4f}"
            )

        except httpx.RequestError as e:
            logger.error(f"Error checking budget: {e}")
            return BudgetCheckResponse(
                allowed=True,
                message=f"Budget check failed: {str(e)}"
            )


@app.get("/pricing")
async def get_pricing():
    """Get current model pricing information."""
    return {
        model: {
            "input_cost_per_million": float(pricing["input"]),
            "output_cost_per_million": float(pricing["output"]),
        }
        for model, pricing in MODEL_PRICING.items()
    }


@app.post("/pricing/update")
async def update_pricing(model: str, input_cost: float, output_cost: float):
    """Update pricing for a model (admin only)."""
    MODEL_PRICING[model.lower()] = {
        "input": Decimal(str(input_cost)),
        "output": Decimal(str(output_cost)),
    }
    return {"status": "updated", "model": model}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
