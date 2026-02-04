"""
Temporal A2A Runtime Service for AI Gateway Platform.

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
import os
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum

from fastapi import FastAPI, HTTPException, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx
from temporalio.client import Client as TemporalClient
from temporalio.worker import Worker
from temporalio import workflow, activity
from temporalio.common import RetryPolicy
from temporalio.worker.workflow_sandbox import SandboxedWorkflowRunner, SandboxRestrictions
import redis.asyncio as redis
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


# Configuration
TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "localhost:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")
TEMPORAL_TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "a2a-agents")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
AGENT_GATEWAY_URL = os.getenv("AGENT_GATEWAY_URL", "http://localhost:9000")
LITELLM_URL = os.getenv("LITELLM_URL", "http://localhost:4000")
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

# OpenTelemetry setup
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

if OTEL_ENDPOINT:
    otlp_exporter = OTLPSpanExporter(endpoint=OTEL_ENDPOINT, insecure=True)
    trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))


# Enums
class AgentStatus(str, Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"


class MessagePriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_HUMAN = "waiting_human"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Pydantic Models
class AgentCapability(BaseModel):
    """Agent capability definition."""
    name: str
    description: str
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None


class Agent(BaseModel):
    """Agent registration."""
    id: str
    name: str
    description: str
    endpoint: str
    capabilities: List[AgentCapability]
    status: AgentStatus = AgentStatus.AVAILABLE
    metadata: Dict[str, Any] = Field(default_factory=dict)
    registered_at: Optional[str] = None
    last_heartbeat: Optional[str] = None


class AgentMessage(BaseModel):
    """Message between agents."""
    id: Optional[str] = None
    source_agent: str
    target_agent: str
    content: Dict[str, Any]
    priority: MessagePriority = MessagePriority.NORMAL
    reply_to: Optional[str] = None
    correlation_id: Optional[str] = None
    created_at: Optional[str] = None


class A2AWorkflowRequest(BaseModel):
    """Request to start an A2A workflow."""
    workflow_type: str  # single_agent, sequential, parallel, supervisor
    agents: List[str]
    input: Dict[str, Any]
    options: Dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = 3600
    require_human_approval: bool = False


class A2AWorkflowResponse(BaseModel):
    """Response from workflow operations."""
    workflow_id: str
    status: WorkflowStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class HumanApprovalRequest(BaseModel):
    """Human approval for workflow step."""
    workflow_id: str
    step_id: str
    approved: bool
    comment: Optional[str] = None
    approver: Optional[str] = None


# Activity Data Classes
@dataclass
class InvokeAgentInput:
    agent_id: str
    capability: str
    input_data: Dict[str, Any]
    timeout_seconds: int = 300


@dataclass
class InvokeAgentOutput:
    success: bool
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    tokens_used: int
    duration_ms: int


# Temporal Activities
@activity.defn
async def invoke_agent(input: InvokeAgentInput) -> InvokeAgentOutput:
    """Invoke an agent with the given capability."""
    start_time = datetime.utcnow()

    async with httpx.AsyncClient(timeout=input.timeout_seconds) as client:
        try:
            # Get agent endpoint from registry
            agent_data = await redis_client.hget("a2a:agents", input.agent_id)
            if not agent_data:
                return InvokeAgentOutput(
                    success=False,
                    result=None,
                    error=f"Agent {input.agent_id} not found",
                    tokens_used=0,
                    duration_ms=0,
                )

            agent = Agent(**json.loads(agent_data))

            # Invoke the agent
            response = await client.post(
                f"{agent.endpoint}/invoke",
                json={
                    "capability": input.capability,
                    "input": input.input_data,
                },
            )

            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            if response.status_code == 200:
                result = response.json()
                return InvokeAgentOutput(
                    success=True,
                    result=result.get("result"),
                    error=None,
                    tokens_used=result.get("tokens_used", 0),
                    duration_ms=duration_ms,
                )
            else:
                return InvokeAgentOutput(
                    success=False,
                    result=None,
                    error=f"Agent returned status {response.status_code}: {response.text}",
                    tokens_used=0,
                    duration_ms=duration_ms,
                )

        except Exception as e:
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            return InvokeAgentOutput(
                success=False,
                result=None,
                error=str(e),
                tokens_used=0,
                duration_ms=duration_ms,
            )


@activity.defn
async def send_message(message: Dict[str, Any]) -> bool:
    """Send a message to an agent."""
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            agent_data = await redis_client.hget("a2a:agents", message["target_agent"])
            if not agent_data:
                return False

            agent = Agent(**json.loads(agent_data))

            response = await client.post(
                f"{agent.endpoint}/messages",
                json=message,
            )
            return response.status_code == 200
        except Exception:
            return False


@activity.defn
async def wait_for_human_approval(workflow_id: str, step_id: str, timeout_seconds: int) -> Dict[str, Any]:
    """Wait for human approval on a workflow step."""
    key = f"a2a:approvals:{workflow_id}:{step_id}"
    deadline = datetime.utcnow() + timedelta(seconds=timeout_seconds)

    while datetime.utcnow() < deadline:
        approval_data = await redis_client.get(key)
        if approval_data:
            return json.loads(approval_data)
        await asyncio.sleep(5)

    raise TimeoutError(f"Human approval timed out after {timeout_seconds} seconds")


@activity.defn
async def record_execution_step(
    workflow_id: str,
    step_name: str,
    status: str,
    input_data: Dict[str, Any],
    output_data: Optional[Dict[str, Any]],
    error: Optional[str],
) -> None:
    """Record workflow execution step for audit."""
    step = {
        "workflow_id": workflow_id,
        "step_name": step_name,
        "status": status,
        "input": input_data,
        "output": output_data,
        "error": error,
        "timestamp": datetime.utcnow().isoformat(),
    }
    await redis_client.rpush(f"a2a:history:{workflow_id}", json.dumps(step))


# Temporal Workflows
@workflow.defn
class SingleAgentWorkflow:
    """Workflow for single agent invocation with retries."""

    @workflow.run
    async def run(self, agent_id: str, capability: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        workflow_id = workflow.info().workflow_id

        # Record start
        await workflow.execute_activity(
            record_execution_step,
            args=[workflow_id, "start", "running", input_data, None, None],
            start_to_close_timeout=timedelta(seconds=30),
        )

        # Invoke agent with retry policy
        result = await workflow.execute_activity(
            invoke_agent,
            InvokeAgentInput(
                agent_id=agent_id,
                capability=capability,
                input_data=input_data,
            ),
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(minutes=1),
                maximum_attempts=3,
            ),
        )

        # Record completion
        await workflow.execute_activity(
            record_execution_step,
            args=[workflow_id, "complete", "completed" if result.success else "failed", {}, result.result, result.error],
            start_to_close_timeout=timedelta(seconds=30),
        )

        if not result.success:
            raise Exception(result.error)

        return {
            "result": result.result,
            "tokens_used": result.tokens_used,
            "duration_ms": result.duration_ms,
        }


@workflow.defn
class SequentialAgentWorkflow:
    """Workflow for sequential agent invocations (pipeline)."""

    @workflow.run
    async def run(self, agents: List[Dict[str, str]], initial_input: Dict[str, Any]) -> Dict[str, Any]:
        workflow_id = workflow.info().workflow_id
        current_input = initial_input
        results = []

        for i, agent_config in enumerate(agents):
            agent_id = agent_config["agent_id"]
            capability = agent_config["capability"]
            step_name = f"agent_{i}_{agent_id}"

            # Record step start
            await workflow.execute_activity(
                record_execution_step,
                args=[workflow_id, step_name, "running", current_input, None, None],
                start_to_close_timeout=timedelta(seconds=30),
            )

            # Invoke agent
            result = await workflow.execute_activity(
                invoke_agent,
                InvokeAgentInput(
                    agent_id=agent_id,
                    capability=capability,
                    input_data=current_input,
                ),
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )

            if not result.success:
                await workflow.execute_activity(
                    record_execution_step,
                    args=[workflow_id, step_name, "failed", current_input, None, result.error],
                    start_to_close_timeout=timedelta(seconds=30),
                )
                raise Exception(f"Agent {agent_id} failed: {result.error}")

            # Record step completion
            await workflow.execute_activity(
                record_execution_step,
                args=[workflow_id, step_name, "completed", current_input, result.result, None],
                start_to_close_timeout=timedelta(seconds=30),
            )

            results.append({
                "agent_id": agent_id,
                "result": result.result,
                "tokens_used": result.tokens_used,
            })

            # Pass output to next agent
            current_input = result.result or {}

        return {
            "final_result": current_input,
            "steps": results,
        }


@workflow.defn
class ParallelAgentWorkflow:
    """Workflow for parallel agent invocations."""

    @workflow.run
    async def run(self, agents: List[Dict[str, str]], input_data: Dict[str, Any]) -> Dict[str, Any]:
        workflow_id = workflow.info().workflow_id

        # Start all agents in parallel
        tasks = []
        for agent_config in agents:
            task = workflow.execute_activity(
                invoke_agent,
                InvokeAgentInput(
                    agent_id=agent_config["agent_id"],
                    capability=agent_config["capability"],
                    input_data=input_data,
                ),
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            tasks.append((agent_config["agent_id"], task))

        # Wait for all to complete
        results = {}
        errors = []

        for agent_id, task in tasks:
            try:
                result = await task
                if result.success:
                    results[agent_id] = result.result
                else:
                    errors.append(f"{agent_id}: {result.error}")
            except Exception as e:
                errors.append(f"{agent_id}: {str(e)}")

        return {
            "results": results,
            "errors": errors if errors else None,
            "success_count": len(results),
            "failure_count": len(errors),
        }


@workflow.defn
class SupervisorAgentWorkflow:
    """Workflow with a supervisor agent coordinating worker agents."""

    @workflow.run
    async def run(
        self,
        supervisor_id: str,
        worker_agents: List[str],
        task: Dict[str, Any],
        max_iterations: int = 10,
    ) -> Dict[str, Any]:
        workflow_id = workflow.info().workflow_id
        iteration = 0
        context = {"task": task, "results": [], "status": "in_progress"}

        while iteration < max_iterations:
            iteration += 1

            # Ask supervisor what to do next
            supervisor_result = await workflow.execute_activity(
                invoke_agent,
                InvokeAgentInput(
                    agent_id=supervisor_id,
                    capability="coordinate",
                    input_data={
                        "context": context,
                        "available_agents": worker_agents,
                        "iteration": iteration,
                    },
                ),
                start_to_close_timeout=timedelta(minutes=5),
            )

            if not supervisor_result.success:
                raise Exception(f"Supervisor failed: {supervisor_result.error}")

            decision = supervisor_result.result or {}
            action = decision.get("action", "complete")

            if action == "complete":
                context["status"] = "completed"
                context["final_result"] = decision.get("result")
                break

            elif action == "delegate":
                # Delegate to a worker agent
                worker_id = decision.get("agent_id")
                worker_capability = decision.get("capability", "execute")
                worker_input = decision.get("input", {})

                worker_result = await workflow.execute_activity(
                    invoke_agent,
                    InvokeAgentInput(
                        agent_id=worker_id,
                        capability=worker_capability,
                        input_data=worker_input,
                    ),
                    start_to_close_timeout=timedelta(minutes=10),
                    retry_policy=RetryPolicy(maximum_attempts=2),
                )

                context["results"].append({
                    "iteration": iteration,
                    "agent": worker_id,
                    "success": worker_result.success,
                    "result": worker_result.result,
                    "error": worker_result.error,
                })

            elif action == "parallel":
                # Run multiple agents in parallel
                parallel_agents = decision.get("agents", [])
                parallel_input = decision.get("input", {})

                tasks = []
                for agent_id in parallel_agents:
                    task = workflow.execute_activity(
                        invoke_agent,
                        InvokeAgentInput(
                            agent_id=agent_id,
                            capability="execute",
                            input_data=parallel_input,
                        ),
                        start_to_close_timeout=timedelta(minutes=10),
                    )
                    tasks.append((agent_id, task))

                parallel_results = {}
                for agent_id, task in tasks:
                    result = await task
                    parallel_results[agent_id] = {
                        "success": result.success,
                        "result": result.result,
                        "error": result.error,
                    }

                context["results"].append({
                    "iteration": iteration,
                    "type": "parallel",
                    "results": parallel_results,
                })

        return context


@workflow.defn
class HumanInLoopWorkflow:
    """Workflow with human approval steps."""

    @workflow.run
    async def run(
        self,
        agent_id: str,
        capability: str,
        input_data: Dict[str, Any],
        approval_timeout_seconds: int = 3600,
    ) -> Dict[str, Any]:
        workflow_id = workflow.info().workflow_id

        # Execute agent
        result = await workflow.execute_activity(
            invoke_agent,
            InvokeAgentInput(
                agent_id=agent_id,
                capability=capability,
                input_data=input_data,
            ),
            start_to_close_timeout=timedelta(minutes=10),
        )

        if not result.success:
            raise Exception(result.error)

        # Wait for human approval
        approval = await workflow.execute_activity(
            wait_for_human_approval,
            args=[workflow_id, "review", approval_timeout_seconds],
            start_to_close_timeout=timedelta(seconds=approval_timeout_seconds + 60),
        )

        if not approval.get("approved"):
            return {
                "status": "rejected",
                "result": result.result,
                "rejection_reason": approval.get("comment"),
            }

        return {
            "status": "approved",
            "result": result.result,
            "approval": approval,
        }


# Global state
redis_client: Optional[redis.Redis] = None
temporal_client: Optional[TemporalClient] = None
worker: Optional[Worker] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global redis_client, temporal_client, worker

    # Startup
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)

    try:
        temporal_client = await TemporalClient.connect(TEMPORAL_HOST, namespace=TEMPORAL_NAMESPACE)

        # Start worker in background with relaxed sandbox for development
        worker = Worker(
            temporal_client,
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

        asyncio.create_task(worker.run())
    except Exception as e:
        print(f"Warning: Could not connect to Temporal: {e}")
        temporal_client = None

    yield

    # Shutdown
    if worker:
        worker.shutdown()
    if redis_client:
        await redis_client.close()


app = FastAPI(
    title="A2A Runtime Service",
    description="Temporal-based agent-to-agent orchestration runtime",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OpenTelemetry instrumentation
FastAPIInstrumentor.instrument_app(app)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    redis_ok = False
    temporal_ok = False

    try:
        await redis_client.ping()
        redis_ok = True
    except Exception:
        pass

    temporal_ok = temporal_client is not None

    return {
        "status": "healthy" if (redis_ok and temporal_ok) else "degraded",
        "redis": "connected" if redis_ok else "disconnected",
        "temporal": "connected" if temporal_ok else "disconnected",
        "task_queue": TEMPORAL_TASK_QUEUE,
    }


# Agent Registry Endpoints
@app.post("/agents/register")
async def register_agent(agent: Agent):
    """Register an agent in the registry."""
    agent.registered_at = datetime.utcnow().isoformat()
    agent.last_heartbeat = agent.registered_at

    await redis_client.hset("a2a:agents", agent.id, agent.model_dump_json())

    # Index capabilities
    for cap in agent.capabilities:
        await redis_client.sadd(f"a2a:capabilities:{cap.name}", agent.id)

    return {"status": "registered", "agent_id": agent.id}


@app.delete("/agents/{agent_id}")
async def unregister_agent(agent_id: str):
    """Unregister an agent."""
    agent_data = await redis_client.hget("a2a:agents", agent_id)
    if agent_data:
        agent = Agent(**json.loads(agent_data))
        for cap in agent.capabilities:
            await redis_client.srem(f"a2a:capabilities:{cap.name}", agent_id)

    await redis_client.hdel("a2a:agents", agent_id)
    return {"status": "unregistered", "agent_id": agent_id}


@app.post("/agents/{agent_id}/heartbeat")
async def agent_heartbeat(agent_id: str):
    """Update agent heartbeat."""
    agent_data = await redis_client.hget("a2a:agents", agent_id)
    if not agent_data:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent = Agent(**json.loads(agent_data))
    agent.last_heartbeat = datetime.utcnow().isoformat()
    agent.status = AgentStatus.AVAILABLE

    await redis_client.hset("a2a:agents", agent_id, agent.model_dump_json())
    return {"status": "ok"}


@app.get("/agents")
async def list_agents(capability: Optional[str] = None):
    """List registered agents."""
    if capability:
        agent_ids = await redis_client.smembers(f"a2a:capabilities:{capability}")
        agents = []
        for agent_id in agent_ids:
            data = await redis_client.hget("a2a:agents", agent_id)
            if data:
                agents.append(json.loads(data))
        return {"agents": agents}

    all_agents = await redis_client.hgetall("a2a:agents")
    return {"agents": [json.loads(v) for v in all_agents.values()]}


@app.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Get agent details."""
    data = await redis_client.hget("a2a:agents", agent_id)
    if not data:
        raise HTTPException(status_code=404, detail="Agent not found")
    return json.loads(data)


@app.get("/capabilities")
async def list_capabilities():
    """List all available capabilities."""
    capabilities = {}
    async for key in redis_client.scan_iter(match="a2a:capabilities:*"):
        cap_name = key.split(":")[-1]
        agent_ids = await redis_client.smembers(key)
        capabilities[cap_name] = list(agent_ids)
    return {"capabilities": capabilities}


# Workflow Endpoints
@app.post("/workflows/start", response_model=A2AWorkflowResponse)
async def start_workflow(request: A2AWorkflowRequest):
    """Start a new A2A workflow."""
    if not temporal_client:
        raise HTTPException(status_code=503, detail="Temporal not available")

    import uuid
    workflow_id = f"a2a-{request.workflow_type}-{uuid.uuid4().hex[:8]}"

    try:
        if request.workflow_type == "single_agent":
            handle = await temporal_client.start_workflow(
                SingleAgentWorkflow.run,
                args=[
                    request.agents[0],
                    request.input.get("capability", "execute"),
                    request.input,
                ],
                id=workflow_id,
                task_queue=TEMPORAL_TASK_QUEUE,
                execution_timeout=timedelta(seconds=request.timeout_seconds),
            )

        elif request.workflow_type == "sequential":
            agents_config = [
                {"agent_id": a, "capability": request.input.get("capability", "execute")}
                for a in request.agents
            ]
            handle = await temporal_client.start_workflow(
                SequentialAgentWorkflow.run,
                args=[agents_config, request.input],
                id=workflow_id,
                task_queue=TEMPORAL_TASK_QUEUE,
                execution_timeout=timedelta(seconds=request.timeout_seconds),
            )

        elif request.workflow_type == "parallel":
            agents_config = [
                {"agent_id": a, "capability": request.input.get("capability", "execute")}
                for a in request.agents
            ]
            handle = await temporal_client.start_workflow(
                ParallelAgentWorkflow.run,
                args=[agents_config, request.input],
                id=workflow_id,
                task_queue=TEMPORAL_TASK_QUEUE,
                execution_timeout=timedelta(seconds=request.timeout_seconds),
            )

        elif request.workflow_type == "supervisor":
            supervisor = request.agents[0]
            workers = request.agents[1:]
            handle = await temporal_client.start_workflow(
                SupervisorAgentWorkflow.run,
                args=[supervisor, workers, request.input, request.options.get("max_iterations", 10)],
                id=workflow_id,
                task_queue=TEMPORAL_TASK_QUEUE,
                execution_timeout=timedelta(seconds=request.timeout_seconds),
            )

        elif request.workflow_type == "human_in_loop":
            handle = await temporal_client.start_workflow(
                HumanInLoopWorkflow.run,
                args=[
                    request.agents[0],
                    request.input.get("capability", "execute"),
                    request.input,
                    request.options.get("approval_timeout", 3600),
                ],
                id=workflow_id,
                task_queue=TEMPORAL_TASK_QUEUE,
                execution_timeout=timedelta(seconds=request.timeout_seconds),
            )

        else:
            raise HTTPException(status_code=400, detail=f"Unknown workflow type: {request.workflow_type}")

        return A2AWorkflowResponse(
            workflow_id=workflow_id,
            status=WorkflowStatus.RUNNING,
            started_at=datetime.utcnow().isoformat(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/workflows/{workflow_id}", response_model=A2AWorkflowResponse)
async def get_workflow_status(workflow_id: str):
    """Get workflow status."""
    if not temporal_client:
        raise HTTPException(status_code=503, detail="Temporal not available")

    try:
        handle = temporal_client.get_workflow_handle(workflow_id)
        desc = await handle.describe()

        status = WorkflowStatus.RUNNING
        if desc.status.name == "COMPLETED":
            status = WorkflowStatus.COMPLETED
        elif desc.status.name == "FAILED":
            status = WorkflowStatus.FAILED
        elif desc.status.name == "CANCELLED":
            status = WorkflowStatus.CANCELLED

        result = None
        error = None
        if status == WorkflowStatus.COMPLETED:
            result = await handle.result()
        elif status == WorkflowStatus.FAILED:
            try:
                await handle.result()
            except Exception as e:
                error = str(e)

        return A2AWorkflowResponse(
            workflow_id=workflow_id,
            status=status,
            result=result,
            error=error,
            started_at=desc.start_time.isoformat() if desc.start_time else None,
            completed_at=desc.close_time.isoformat() if desc.close_time else None,
        )

    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {e}")


@app.post("/workflows/{workflow_id}/cancel")
async def cancel_workflow(workflow_id: str):
    """Cancel a running workflow."""
    if not temporal_client:
        raise HTTPException(status_code=503, detail="Temporal not available")

    try:
        handle = temporal_client.get_workflow_handle(workflow_id)
        await handle.cancel()
        return {"status": "cancelled", "workflow_id": workflow_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/workflows/{workflow_id}/history")
async def get_workflow_history(workflow_id: str):
    """Get workflow execution history."""
    history = await redis_client.lrange(f"a2a:history:{workflow_id}", 0, -1)
    return {"workflow_id": workflow_id, "steps": [json.loads(h) for h in history]}


# Human Approval Endpoints
@app.post("/approvals")
async def submit_approval(approval: HumanApprovalRequest):
    """Submit human approval for a workflow step."""
    key = f"a2a:approvals:{approval.workflow_id}:{approval.step_id}"
    await redis_client.set(
        key,
        json.dumps({
            "approved": approval.approved,
            "comment": approval.comment,
            "approver": approval.approver,
            "timestamp": datetime.utcnow().isoformat(),
        }),
        ex=86400,  # 24 hour expiry
    )
    return {"status": "submitted"}


@app.get("/approvals/pending")
async def list_pending_approvals():
    """List pending human approvals."""
    pending = []
    async for key in redis_client.scan_iter(match="a2a:approvals:*:*"):
        data = await redis_client.get(key)
        if not data:
            parts = key.split(":")
            pending.append({
                "workflow_id": parts[2],
                "step_id": parts[3],
            })
    return {"pending": pending}


# Messaging Endpoints
@app.post("/messages")
async def send_agent_message(message: AgentMessage):
    """Send a message between agents."""
    import uuid
    message.id = str(uuid.uuid4())
    message.created_at = datetime.utcnow().isoformat()

    # Store message
    await redis_client.rpush(
        f"a2a:messages:{message.target_agent}",
        message.model_dump_json(),
    )

    # Notify target agent (best effort)
    try:
        agent_data = await redis_client.hget("a2a:agents", message.target_agent)
        if agent_data:
            agent = Agent(**json.loads(agent_data))
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(f"{agent.endpoint}/messages/notify", json={"message_id": message.id})
    except Exception:
        pass

    return {"status": "sent", "message_id": message.id}


@app.get("/messages/{agent_id}")
async def get_agent_messages(agent_id: str, limit: int = 100):
    """Get messages for an agent."""
    messages = await redis_client.lrange(f"a2a:messages:{agent_id}", 0, limit - 1)
    return {"messages": [json.loads(m) for m in messages]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8087)
