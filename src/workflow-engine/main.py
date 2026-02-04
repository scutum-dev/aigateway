"""
LangGraph Workflow Engine Service

A FastAPI service for orchestrating multi-step AI workflows with:
- LangGraph state graphs (sequential, parallel, cyclic)
- Pre-built templates (research, coding, data analysis)
- MCP tool binding via Agent Gateway
- PostgreSQL checkpointing for state persistence
- Per-workflow cost tracking
- WebSocket streaming for execution updates
"""

import os
import logging
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
import asyncpg

from config import config
from models.workflow import WorkflowInput, WorkflowOutput, WorkflowTemplate
from models.execution import WorkflowExecution, ExecutionStatus
from persistence.repository import WorkflowRepository
from persistence.checkpointer import create_checkpointer
from tools.llm_client import LLMClient
from tools.mcp_binding import MCPClient
from templates import ResearchAgentWorkflow, CodingAgentWorkflow, DataAnalysisWorkflow
from api.routes import router, set_dependencies
from api.websocket import websocket_endpoint, send_execution_update

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Global resources
db_pool: Optional[asyncpg.Pool] = None
repository: Optional[WorkflowRepository] = None
checkpointer: Optional[Any] = None
llm_client: Optional[LLMClient] = None
mcp_client: Optional[MCPClient] = None


class WorkflowManager:
    """Manages workflow execution."""

    def __init__(
        self,
        repository: WorkflowRepository,
        checkpointer: Any,
        llm_client: LLMClient,
        mcp_client: MCPClient,
    ):
        self.repository = repository
        self.checkpointer = checkpointer
        self.llm_client = llm_client
        self.mcp_client = mcp_client
        self._running_executions: Dict[str, asyncio.Task] = {}

    def _get_workflow(self, template: WorkflowTemplate):
        """Get workflow instance for template type."""
        workflows = {
            WorkflowTemplate.RESEARCH: ResearchAgentWorkflow,
            WorkflowTemplate.CODING: CodingAgentWorkflow,
            WorkflowTemplate.DATA_ANALYSIS: DataAnalysisWorkflow,
        }

        workflow_class = workflows.get(template)
        if not workflow_class:
            raise ValueError(f"Unknown template: {template}")

        return workflow_class(
            checkpointer=self.checkpointer,
            llm_client=self.llm_client,
            mcp_client=self.mcp_client,
        )

    async def start_execution(self, request: WorkflowInput) -> WorkflowOutput:
        """Start a new workflow execution."""
        start_time = datetime.now(timezone.utc)

        # Determine workflow
        if request.template:
            template = request.template
            workflow_name = f"{template.value}_workflow"
        else:
            raise ValueError("Either workflow_id or template must be provided")

        # Create execution record
        execution = WorkflowExecution(
            workflow_name=workflow_name,
            template_type=template.value,
            user_id=request.user_id,
            team_id=request.team_id,
            status=ExecutionStatus.PENDING,
            input=request.input,
        )

        execution_id = await self.repository.create_execution(execution)

        # Update status to running
        await self.repository.update_execution(execution_id, status="running")
        await send_execution_update(execution_id, "status", {"status": "running"})

        try:
            # Get and run workflow
            workflow = self._get_workflow(template)

            # Configure thread ID for checkpointing
            config = {
                "configurable": {
                    "thread_id": execution_id,
                }
            }

            # Run workflow
            final_state = await workflow.run(request.input, config)

            # Calculate duration
            end_time = datetime.now(timezone.utc)
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            # Update execution record
            await self.repository.update_execution(
                execution_id,
                status="completed",
                output=final_state.output,
                total_tokens=final_state.total_tokens,
                total_cost=final_state.total_cost,
                duration_ms=duration_ms,
            )

            await send_execution_update(execution_id, "status", {
                "status": "completed",
                "output": final_state.output,
            })

            return WorkflowOutput(
                execution_id=execution_id,
                status="completed",
                output=final_state.output,
                total_cost=final_state.total_cost,
                total_tokens=final_state.total_tokens,
                duration_ms=duration_ms,
            )

        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")

            await self.repository.update_execution(
                execution_id,
                status="failed",
                error=str(e),
            )

            await send_execution_update(execution_id, "error", {"error": str(e)})

            return WorkflowOutput(
                execution_id=execution_id,
                status="failed",
                error=str(e),
            )

    async def pause_execution(self, execution_id: str):
        """Pause a running execution."""
        # LangGraph with checkpointing supports interruption
        # For now, just update the status
        await self.repository.update_execution(execution_id, status="paused")
        await send_execution_update(execution_id, "status", {"status": "paused"})

    async def resume_execution(self, execution_id: str) -> WorkflowOutput:
        """Resume a paused execution."""
        execution = await self.repository.get_execution(execution_id)
        if not execution:
            raise ValueError(f"Execution not found: {execution_id}")

        if execution.status != ExecutionStatus.PAUSED:
            raise ValueError(f"Execution is not paused: {execution.status}")

        await self.repository.update_execution(execution_id, status="running")
        await send_execution_update(execution_id, "status", {"status": "running"})

        try:
            # Get workflow and resume
            template = WorkflowTemplate(execution.template_type)
            workflow = self._get_workflow(template)

            final_state = await workflow.resume(execution_id)

            await self.repository.update_execution(
                execution_id,
                status="completed",
                output=final_state.output,
                total_tokens=final_state.total_tokens,
                total_cost=final_state.total_cost,
            )

            await send_execution_update(execution_id, "status", {
                "status": "completed",
                "output": final_state.output,
            })

            return WorkflowOutput(
                execution_id=execution_id,
                status="completed",
                output=final_state.output,
                total_cost=final_state.total_cost,
            )

        except Exception as e:
            logger.error(f"Resume failed: {e}")
            await self.repository.update_execution(
                execution_id,
                status="failed",
                error=str(e),
            )
            raise


workflow_manager: Optional[WorkflowManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global db_pool, repository, checkpointer, llm_client, mcp_client, workflow_manager

    # Setup OpenTelemetry
    otel_endpoint = config.otel_endpoint
    resource = Resource.create({"service.name": "workflow-engine"})
    provider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=otel_endpoint))
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    # Create database pool
    try:
        db_pool = await asyncpg.create_pool(config.database_url, min_size=2, max_size=10)
        logger.info("Database connection established")

        # Initialize repository
        repository = WorkflowRepository(db_pool)
        await repository.init_tables()

        # Initialize checkpointer
        checkpointer = await create_checkpointer(config.database_url)

    except Exception as e:
        logger.warning(f"Could not connect to database: {e}")

    # Create clients
    llm_client = LLMClient(
        base_url=config.litellm_url,
        api_key=config.litellm_api_key,
    )
    mcp_client = MCPClient(base_url=config.agent_gateway_url)

    # Create workflow manager
    if repository:
        workflow_manager = WorkflowManager(
            repository=repository,
            checkpointer=checkpointer,
            llm_client=llm_client,
            mcp_client=mcp_client,
        )
        set_dependencies(repository, workflow_manager)

    logger.info("Workflow engine service started")
    yield

    # Cleanup
    await llm_client.close()
    await mcp_client.close()
    if db_pool:
        await db_pool.close()

    logger.info("Workflow engine service stopped")


app = FastAPI(
    title="LangGraph Workflow Engine",
    description="Multi-step AI workflow orchestration with LangGraph",
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

# Include API routes
app.include_router(router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.websocket("/ws/executions/{execution_id}")
async def execution_websocket(websocket: WebSocket, execution_id: str):
    """WebSocket endpoint for execution streaming."""
    await websocket_endpoint(websocket, execution_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.host, port=config.port)
