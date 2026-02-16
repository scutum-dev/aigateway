import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException

import state
from config import TEMPORAL_TASK_QUEUE
from a2a_models import A2AWorkflowRequest, A2AWorkflowResponse, WorkflowStatus
from workflows import (
    SingleAgentWorkflow,
    SequentialAgentWorkflow,
    ParallelAgentWorkflow,
    SupervisorAgentWorkflow,
    HumanInLoopWorkflow,
)

router = APIRouter(tags=["Workflows"])


@router.post("/workflows/start", response_model=A2AWorkflowResponse)
async def start_workflow(request: A2AWorkflowRequest):
    """Start a new A2A workflow."""
    if not state.temporal_client:
        raise HTTPException(status_code=503, detail="Temporal not available")

    workflow_id = f"a2a-{request.workflow_type}-{uuid.uuid4().hex[:8]}"

    try:
        if request.workflow_type == "single_agent":
            handle = await state.temporal_client.start_workflow(
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
            handle = await state.temporal_client.start_workflow(
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
            handle = await state.temporal_client.start_workflow(
                ParallelAgentWorkflow.run,
                args=[agents_config, request.input],
                id=workflow_id,
                task_queue=TEMPORAL_TASK_QUEUE,
                execution_timeout=timedelta(seconds=request.timeout_seconds),
            )

        elif request.workflow_type == "supervisor":
            supervisor = request.agents[0]
            workers = request.agents[1:]
            handle = await state.temporal_client.start_workflow(
                SupervisorAgentWorkflow.run,
                args=[supervisor, workers, request.input, request.options.get("max_iterations", 10)],
                id=workflow_id,
                task_queue=TEMPORAL_TASK_QUEUE,
                execution_timeout=timedelta(seconds=request.timeout_seconds),
            )

        elif request.workflow_type == "human_in_loop":
            handle = await state.temporal_client.start_workflow(
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
            started_at=datetime.now(timezone.utc).isoformat(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflows/{workflow_id}", response_model=A2AWorkflowResponse)
async def get_workflow_status(workflow_id: str):
    """Get workflow status."""
    if not state.temporal_client:
        raise HTTPException(status_code=503, detail="Temporal not available")

    try:
        handle = state.temporal_client.get_workflow_handle(workflow_id)
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


@router.post("/workflows/{workflow_id}/cancel")
async def cancel_workflow(workflow_id: str):
    """Cancel a running workflow."""
    if not state.temporal_client:
        raise HTTPException(status_code=503, detail="Temporal not available")

    try:
        handle = state.temporal_client.get_workflow_handle(workflow_id)
        await handle.cancel()
        return {"status": "cancelled", "workflow_id": workflow_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflows/{workflow_id}/history")
async def get_workflow_history(workflow_id: str):
    """Get workflow execution history."""
    history = await state.redis_client.lrange(f"a2a:history:{workflow_id}", 0, -1)
    return {"workflow_id": workflow_id, "steps": [json.loads(h) for h in history]}
