import json
from typing import List

from fastapi import APIRouter, HTTPException, Depends
import httpx

import deps
from auth import get_current_user, require_admin, UserInfo
from models import WorkflowSummary, WorkflowCreate, WorkflowExecuteRequest

router = APIRouter()


@router.get("/workflows", response_model=List[WorkflowSummary])
async def list_workflows(user: UserInfo = Depends(get_current_user)):
    """List all workflow definitions."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
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


@router.post("/workflows", response_model=WorkflowSummary)
async def create_workflow(
    workflow: WorkflowCreate,
    user: UserInfo = Depends(require_admin)
):
    """Create a new workflow definition."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
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


@router.get("/workflow-templates")
async def list_workflow_templates(user: UserInfo = Depends(get_current_user)):
    """List available workflow templates from the Workflow Engine."""
    try:
        response = await deps.http_client.get(
            f"{deps.WORKFLOW_ENGINE_URL}/api/v1/templates",
            headers=deps._internal_headers(),
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/workflow-executions")
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
        response = await deps.http_client.post(
            f"{deps.WORKFLOW_ENGINE_URL}/api/v1/executions",
            json=payload,
            headers=deps._internal_headers(),
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/workflow-executions")
async def list_workflow_executions(user: UserInfo = Depends(get_current_user)):
    """List workflow executions from the Workflow Engine."""
    try:
        response = await deps.http_client.get(
            f"{deps.WORKFLOW_ENGINE_URL}/api/v1/executions",
            headers=deps._internal_headers(),
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/workflow-executions/{execution_id}")
async def get_workflow_execution(
    execution_id: str,
    user: UserInfo = Depends(get_current_user)
):
    """Get a specific workflow execution from the Workflow Engine."""
    try:
        response = await deps.http_client.get(
            f"{deps.WORKFLOW_ENGINE_URL}/api/v1/executions/{execution_id}",
            headers=deps._internal_headers(),
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
