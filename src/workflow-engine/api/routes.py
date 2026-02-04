"""
REST API routes for workflow engine.
"""

import logging
from typing import Optional, List
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Depends

from models.workflow import WorkflowDefinition, WorkflowInput, WorkflowOutput, WorkflowTemplate
from models.execution import WorkflowExecution, ExecutionStatus, ExecutionSummary, CostSummary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["workflows"])


# These will be set by the main app
_repository = None
_workflow_manager = None


def set_dependencies(repository, workflow_manager):
    """Set dependencies from main app."""
    global _repository, _workflow_manager
    _repository = repository
    _workflow_manager = workflow_manager


# Workflow Definitions

@router.post("/workflows", response_model=dict)
async def create_workflow(workflow: WorkflowDefinition):
    """Create a new workflow definition."""
    if not _repository:
        raise HTTPException(status_code=503, detail="Service not ready")

    try:
        workflow_id = await _repository.create_workflow(workflow)
        return {"id": workflow_id, "name": workflow.name}
    except Exception as e:
        logger.error(f"Failed to create workflow: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/workflows", response_model=List[dict])
async def list_workflows(active_only: bool = Query(default=True)):
    """List all workflow definitions."""
    if not _repository:
        raise HTTPException(status_code=503, detail="Service not ready")

    workflows = await _repository.list_workflows(active_only=active_only)
    return [
        {
            "id": w.id,
            "name": w.name,
            "version": w.version,
            "template_type": w.template_type,
            "description": w.description,
            "is_active": w.is_active,
        }
        for w in workflows
    ]


@router.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    """Get a workflow definition by ID."""
    if not _repository:
        raise HTTPException(status_code=503, detail="Service not ready")

    workflow = await _repository.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    return workflow


# Templates

@router.get("/templates")
async def list_templates():
    """List available pre-built workflow templates."""
    return {
        "templates": [
            {
                "type": WorkflowTemplate.RESEARCH.value,
                "name": "Research Agent",
                "description": "Multi-source research with web search, database queries, and report generation",
                "nodes": ["parse_query", "search_web", "search_database", "analyze_results", "generate_report"],
            },
            {
                "type": WorkflowTemplate.CODING.value,
                "name": "Coding Agent",
                "description": "Iterative code generation with analysis and refinement",
                "nodes": ["understand_task", "read_code", "generate_code", "analyze_code", "finalize_code"],
            },
            {
                "type": WorkflowTemplate.DATA_ANALYSIS.value,
                "name": "Data Analysis Agent",
                "description": "SQL query generation, data analysis, and visualization recommendations",
                "nodes": ["parse_question", "query_data", "analyze_data", "generate_visualization", "summarize"],
            },
        ]
    }


# Executions

@router.post("/executions", response_model=WorkflowOutput)
async def start_execution(request: WorkflowInput):
    """Start a new workflow execution."""
    if not _workflow_manager:
        raise HTTPException(status_code=503, detail="Service not ready")

    try:
        result = await _workflow_manager.start_execution(request)
        return result
    except Exception as e:
        logger.error(f"Failed to start execution: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/executions", response_model=List[ExecutionSummary])
async def list_executions(
    user_id: Optional[str] = None,
    team_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
):
    """List workflow executions."""
    if not _repository:
        raise HTTPException(status_code=503, detail="Service not ready")

    return await _repository.list_executions(
        user_id=user_id,
        team_id=team_id,
        status=status,
        limit=limit,
    )


@router.get("/executions/{execution_id}")
async def get_execution(execution_id: str):
    """Get execution details."""
    if not _repository:
        raise HTTPException(status_code=503, detail="Service not ready")

    execution = await _repository.get_execution(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    return execution


@router.get("/executions/{execution_id}/steps")
async def get_execution_steps(execution_id: str):
    """Get all steps for an execution."""
    if not _repository:
        raise HTTPException(status_code=503, detail="Service not ready")

    steps = await _repository.get_steps(execution_id)
    return {"steps": steps}


@router.post("/executions/{execution_id}/pause")
async def pause_execution(execution_id: str):
    """Pause a running execution."""
    if not _workflow_manager:
        raise HTTPException(status_code=503, detail="Service not ready")

    try:
        await _workflow_manager.pause_execution(execution_id)
        return {"status": "paused", "execution_id": execution_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/executions/{execution_id}/resume")
async def resume_execution(execution_id: str):
    """Resume a paused execution."""
    if not _workflow_manager:
        raise HTTPException(status_code=503, detail="Service not ready")

    try:
        result = await _workflow_manager.resume_execution(execution_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/executions/{execution_id}/cancel")
async def cancel_execution(execution_id: str):
    """Cancel an execution."""
    if not _repository:
        raise HTTPException(status_code=503, detail="Service not ready")

    await _repository.update_execution(execution_id, status="cancelled")
    return {"status": "cancelled", "execution_id": execution_id}


# Cost Summary

@router.get("/costs/summary", response_model=CostSummary)
async def get_cost_summary(
    user_id: Optional[str] = None,
    team_id: Optional[str] = None,
    days: int = Query(default=30, le=365),
):
    """Get workflow cost summary."""
    if not _repository:
        raise HTTPException(status_code=503, detail="Service not ready")

    # Get all executions for the period
    executions = await _repository.list_executions(
        user_id=user_id,
        team_id=team_id,
        limit=10000,
    )

    total_cost = sum(e.total_cost for e in executions)
    total_tokens = sum(getattr(e, 'total_tokens', 0) for e in executions if hasattr(e, 'total_tokens'))

    # Aggregate by workflow
    cost_by_workflow = {}
    cost_by_user = {}
    cost_by_team = {}

    for e in executions:
        wf_name = e.workflow_name or "unknown"
        cost_by_workflow[wf_name] = cost_by_workflow.get(wf_name, 0) + e.total_cost

        if e.user_id:
            cost_by_user[e.user_id] = cost_by_user.get(e.user_id, 0) + e.total_cost

    return CostSummary(
        total_executions=len(executions),
        total_cost=total_cost,
        total_tokens=total_tokens,
        average_cost_per_execution=total_cost / len(executions) if executions else 0,
        cost_by_workflow=cost_by_workflow,
        cost_by_user=cost_by_user,
        cost_by_team=cost_by_team,
    )
