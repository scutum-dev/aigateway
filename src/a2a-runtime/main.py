"""
Temporal A2A Runtime Service for AI Control Plane Platform.

Provides agent-to-agent orchestration using Temporal workflows for:
- Durable agent execution with automatic retries
- Long-running agent conversations
- Human-in-the-loop approval workflows
- Multi-agent collaboration patterns
- Agent capability matching and routing

Features:
- Temporal workflow definitions for common patterns
- Activity implementations for agent invocation
- Agent registry with capability discovery
- Message routing and delivery
- Execution history and audit logging
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as redis
from temporalio.client import Client as TemporalClient
from temporalio.worker import Worker
from temporalio.worker.workflow_sandbox import SandboxedWorkflowRunner, SandboxRestrictions
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

import state
from config import (
    TEMPORAL_HOST,
    TEMPORAL_NAMESPACE,
    TEMPORAL_TASK_QUEUE,
    REDIS_URL,
    OTEL_ENDPOINT,
)
from activities import invoke_agent, send_message, wait_for_human_approval, record_execution_step
from workflows import (
    SingleAgentWorkflow,
    SequentialAgentWorkflow,
    ParallelAgentWorkflow,
    SupervisorAgentWorkflow,
    HumanInLoopWorkflow,
)
from routes.agents import router as agents_router
from routes.workflows import router as workflows_router
from routes.approvals import router as approvals_router
from routes.messages import router as messages_router
from shared.cors import get_cors_origins
from shared.middleware import ServiceAuthMiddleware


logger = logging.getLogger(__name__)

# OpenTelemetry setup
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

if OTEL_ENDPOINT:
    otlp_exporter = OTLPSpanExporter(endpoint=OTEL_ENDPOINT, insecure=True)
    trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    state.redis_client = redis.from_url(REDIS_URL, decode_responses=True)

    try:
        state.temporal_client = await TemporalClient.connect(TEMPORAL_HOST, namespace=TEMPORAL_NAMESPACE)

        # Start worker in background with relaxed sandbox for development
        state.worker = Worker(
            state.temporal_client,
            task_queue=TEMPORAL_TASK_QUEUE,
            workflows=[
                SingleAgentWorkflow,
                SequentialAgentWorkflow,
                ParallelAgentWorkflow,
                SupervisorAgentWorkflow,
                HumanInLoopWorkflow,
            ],
            activities=[
                invoke_agent,
                send_message,
                wait_for_human_approval,
                record_execution_step,
            ],
            workflow_runner=SandboxedWorkflowRunner(
                restrictions=SandboxRestrictions.default.with_passthrough_modules("httpx", "redis", "pydantic")
            ),
        )

        asyncio.create_task(state.worker.run())
    except Exception as e:
        print(f"Warning: Could not connect to Temporal: {e}")
        state.temporal_client = None

    yield

    # Shutdown
    if state.worker:
        state.worker.shutdown()
    if state.redis_client:
        await state.redis_client.close()


app = FastAPI(
    title="A2A Runtime Service",
    description="Temporal-based agent-to-agent orchestration runtime",
    version="1.0.0",
    lifespan=lifespan,
)

# Add service auth middleware
app.add_middleware(ServiceAuthMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Service-Key"],
)

# OpenTelemetry instrumentation
FastAPIInstrumentor.instrument_app(app)

# Include routers
app.include_router(agents_router)
app.include_router(workflows_router)
app.include_router(approvals_router)
app.include_router(messages_router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    redis_ok = False
    temporal_ok = False

    try:
        await state.redis_client.ping()
        redis_ok = True
    except Exception:
        pass

    temporal_ok = state.temporal_client is not None

    return {
        "status": "healthy" if (redis_ok and temporal_ok) else "degraded",
        "redis": "connected" if redis_ok else "disconnected",
        "temporal": "connected" if temporal_ok else "disconnected",
        "task_queue": TEMPORAL_TASK_QUEUE,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8087)
