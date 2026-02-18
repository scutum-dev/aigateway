"""Prompt registry router — template management, versioning, approvals, and analytics."""

import json
import re
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

import deps
from auth import UserInfo, get_current_user, require_admin
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class VariableSpec(BaseModel):
    name: str
    type: str = "string"
    required: bool = True
    default: Optional[str] = None


class PromptTemplateCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    category: Optional[str] = None
    template_text: str
    variables: Optional[List[VariableSpec]] = None
    model_hint: Optional[str] = None
    tags: Optional[List[str]] = None


class PromptTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    template_text: Optional[str] = None
    variables: Optional[List[VariableSpec]] = None
    model_hint: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None


class PromptTemplate(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str] = None
    category: Optional[str] = None
    template_text: str
    variables: List[Dict[str, Any]] = []
    version: int
    is_current: bool
    status: str
    team_id: Optional[str] = None
    model_hint: Optional[str] = None
    tags: List[str] = []
    created_by: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PromptApproval(BaseModel):
    id: str
    template_id: str
    template_version: int
    requested_by: str
    reviewer: Optional[str] = None
    status: str
    comment: Optional[str] = None
    requested_at: Optional[str] = None
    reviewed_at: Optional[str] = None


class PromptRenderRequest(BaseModel):
    variables: Dict[str, str] = {}


class PromptUsageStats(BaseModel):
    version: int
    total_uses: int
    avg_latency_ms: Optional[float] = None
    total_cost: Optional[float] = None
    total_input_tokens: Optional[int] = None
    total_output_tokens: Optional[int] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_template(row) -> PromptTemplate:
    variables = row["variables"]
    if isinstance(variables, str):
        variables = json.loads(variables)
    tags = row["tags"] or []
    return PromptTemplate(
        id=str(row["id"]),
        name=row["name"],
        slug=row["slug"],
        description=row["description"],
        category=row["category"],
        template_text=row["template_text"],
        variables=variables if isinstance(variables, list) else [],
        version=row["version"],
        is_current=row["is_current"],
        status=row["status"] or "draft",
        team_id=str(row["team_id"]) if row["team_id"] else None,
        model_hint=row["model_hint"],
        tags=list(tags),
        created_by=row["created_by"],
        approved_by=row["approved_by"],
        approved_at=str(row["approved_at"]) if row["approved_at"] else None,
        is_active=row["is_active"],
        created_at=str(row["created_at"]) if row["created_at"] else None,
        updated_at=str(row["updated_at"]) if row["updated_at"] else None,
    )


def _row_to_approval(row) -> PromptApproval:
    return PromptApproval(
        id=str(row["id"]),
        template_id=str(row["template_id"]),
        template_version=row["template_version"],
        requested_by=row["requested_by"],
        reviewer=row["reviewer"],
        status=row["status"],
        comment=row["comment"],
        requested_at=str(row["requested_at"]) if row["requested_at"] else None,
        reviewed_at=str(row["reviewed_at"]) if row["reviewed_at"] else None,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/prompts", response_model=List[PromptTemplate])
async def list_prompts(
    category: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    tag: Optional[str] = Query(default=None),
    user: UserInfo = Depends(get_current_user),
):
    """List prompt templates with optional filters."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    conditions = ["is_active = true", "is_current = true"]
    params: list = []
    idx = 1

    if category:
        conditions.append(f"category = ${idx}")
        params.append(category)
        idx += 1
    if status:
        conditions.append(f"status = ${idx}")
        params.append(status)
        idx += 1
    if tag:
        conditions.append(f"${idx} = ANY(tags)")
        params.append(tag)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}"
    query = f"""
        SELECT * FROM prompt_templates
        {where}
        ORDER BY updated_at DESC
    """

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        return [_row_to_template(row) for row in rows]


@router.post("/prompts", response_model=PromptTemplate)
async def create_prompt(
    data: PromptTemplateCreate,
    user: UserInfo = Depends(get_current_user),
):
    """Create a new prompt template."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    variables_json = json.dumps([v.model_dump() for v in data.variables]) if data.variables else "[]"
    tags = data.tags or []

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO prompt_templates (name, slug, description, category, template_text, variables, model_hint, tags, created_by)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9)
            RETURNING *
            """,
            data.name,
            data.slug,
            data.description,
            data.category,
            data.template_text,
            variables_json,
            data.model_hint,
            tags,
            user.user_id,
        )
        return _row_to_template(row)


@router.get("/prompts/{slug}", response_model=PromptTemplate)
async def get_prompt(slug: str, user: UserInfo = Depends(get_current_user)):
    """Get the current version of a prompt template by slug."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM prompt_templates WHERE slug = $1 AND is_current = true AND is_active = true",
            slug,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Prompt template not found")
        return _row_to_template(row)


@router.get("/prompts/{slug}/versions", response_model=List[PromptTemplate])
async def list_versions(slug: str, user: UserInfo = Depends(get_current_user)):
    """List all versions of a prompt template."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM prompt_templates WHERE slug = $1 AND is_active = true ORDER BY version DESC",
            slug,
        )
        return [_row_to_template(row) for row in rows]


@router.post("/prompts/{slug}/versions", response_model=PromptTemplate)
async def create_version(
    slug: str,
    data: PromptTemplateUpdate,
    user: UserInfo = Depends(get_current_user),
):
    """Create a new version of an existing prompt template."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        # Get current version
        current = await conn.fetchrow(
            "SELECT * FROM prompt_templates WHERE slug = $1 AND is_current = true AND is_active = true",
            slug,
        )
        if not current:
            raise HTTPException(status_code=404, detail="Prompt template not found")

        new_version = current["version"] + 1

        # Mark old version as not current
        await conn.execute(
            "UPDATE prompt_templates SET is_current = false WHERE slug = $1 AND is_current = true",
            slug,
        )

        # Merge fields: use new data if provided, otherwise carry forward from current
        new_name = data.name if data.name is not None else current["name"]
        new_desc = data.description if data.description is not None else current["description"]
        new_cat = data.category if data.category is not None else current["category"]
        new_text = data.template_text if data.template_text is not None else current["template_text"]
        new_hint = data.model_hint if data.model_hint is not None else current["model_hint"]
        new_tags = data.tags if data.tags is not None else (current["tags"] or [])

        if data.variables is not None:
            new_vars = json.dumps([v.model_dump() for v in data.variables])
        else:
            old_vars = current["variables"]
            new_vars = json.dumps(old_vars) if isinstance(old_vars, list) else (old_vars or "[]")

        row = await conn.fetchrow(
            """
            INSERT INTO prompt_templates (name, slug, description, category, template_text, variables, version, is_current, status, team_id, model_hint, tags, created_by)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, true, 'draft', $8, $9, $10, $11)
            RETURNING *
            """,
            new_name,
            slug,
            new_desc,
            new_cat,
            new_text,
            new_vars,
            new_version,
            current["team_id"],
            new_hint,
            list(new_tags),
            user.user_id,
        )
        return _row_to_template(row)


@router.put("/prompts/{id}", response_model=PromptTemplate)
async def update_prompt(
    id: str,
    data: PromptTemplateUpdate,
    user: UserInfo = Depends(get_current_user),
):
    """Update a prompt template."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    sets: list = []
    params: list = []
    idx = 1

    if data.name is not None:
        sets.append(f"name = ${idx}")
        params.append(data.name)
        idx += 1
    if data.description is not None:
        sets.append(f"description = ${idx}")
        params.append(data.description)
        idx += 1
    if data.category is not None:
        sets.append(f"category = ${idx}")
        params.append(data.category)
        idx += 1
    if data.template_text is not None:
        sets.append(f"template_text = ${idx}")
        params.append(data.template_text)
        idx += 1
    if data.variables is not None:
        sets.append(f"variables = ${idx}::jsonb")
        params.append(json.dumps([v.model_dump() for v in data.variables]))
        idx += 1
    if data.model_hint is not None:
        sets.append(f"model_hint = ${idx}")
        params.append(data.model_hint)
        idx += 1
    if data.tags is not None:
        sets.append(f"tags = ${idx}")
        params.append(data.tags)
        idx += 1
    if data.status is not None:
        sets.append(f"status = ${idx}")
        params.append(data.status)
        idx += 1

    if not sets:
        raise HTTPException(status_code=400, detail="No fields to update")

    sets.append("updated_at = CURRENT_TIMESTAMP")
    params.append(id)

    query = f"""
        UPDATE prompt_templates SET {', '.join(sets)}
        WHERE id = ${idx}::uuid
        RETURNING *
    """

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(query, *params)
        if not row:
            raise HTTPException(status_code=404, detail="Prompt template not found")
        return _row_to_template(row)


@router.delete("/prompts/{id}")
async def delete_prompt(id: str, user: UserInfo = Depends(get_current_user)):
    """Soft delete a prompt template (set is_active=false)."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE prompt_templates SET is_active = false, updated_at = CURRENT_TIMESTAMP WHERE id = $1::uuid",
            id,
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Prompt template not found")
        return {"status": "ok"}


@router.post("/prompts/{slug}/render")
async def render_prompt(
    slug: str,
    data: PromptRenderRequest,
    user: UserInfo = Depends(get_current_user),
):
    """Render a prompt template by substituting {{var}} placeholders."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM prompt_templates WHERE slug = $1 AND is_current = true AND is_active = true",
            slug,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Prompt template not found")

    template_text = row["template_text"]
    rendered = template_text
    for key, value in data.variables.items():
        rendered = rendered.replace("{{" + key + "}}", value)

    # Check for unresolved variables
    unresolved = re.findall(r"\{\{(\w+)\}\}", rendered)

    return {
        "rendered": rendered,
        "unresolved_variables": unresolved,
        "template_version": row["version"],
    }


@router.post("/prompts/{id}/submit-review", response_model=PromptApproval)
async def submit_review(id: str, user: UserInfo = Depends(get_current_user)):
    """Submit a prompt template for approval review."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        template = await conn.fetchrow(
            "SELECT * FROM prompt_templates WHERE id = $1::uuid AND is_active = true",
            id,
        )
        if not template:
            raise HTTPException(status_code=404, detail="Prompt template not found")

        # Update template status to pending_review
        await conn.execute(
            "UPDATE prompt_templates SET status = 'pending_review', updated_at = CURRENT_TIMESTAMP WHERE id = $1::uuid",
            id,
        )

        # Create approval record
        row = await conn.fetchrow(
            """
            INSERT INTO prompt_approvals (template_id, template_version, requested_by)
            VALUES ($1::uuid, $2, $3)
            RETURNING *
            """,
            id,
            template["version"],
            user.user_id,
        )
        return _row_to_approval(row)


@router.get("/prompt-approvals", response_model=List[PromptApproval])
async def list_approvals(
    status: Optional[str] = Query(default="pending"),
    user: UserInfo = Depends(get_current_user),
):
    """List prompt approval requests."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        if status:
            rows = await conn.fetch(
                "SELECT * FROM prompt_approvals WHERE status = $1 ORDER BY requested_at DESC",
                status,
            )
        else:
            rows = await conn.fetch("SELECT * FROM prompt_approvals ORDER BY requested_at DESC")
        return [_row_to_approval(row) for row in rows]


@router.post("/prompt-approvals/{id}/approve")
async def approve_prompt(
    id: str,
    data: Optional[Dict[str, Any]] = None,
    user: UserInfo = Depends(require_admin),
):
    """Approve a prompt template."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    comment = (data or {}).get("comment")

    async with deps.db_pool.acquire() as conn:
        approval = await conn.fetchrow(
            "SELECT * FROM prompt_approvals WHERE id = $1::uuid AND status = 'pending'",
            id,
        )
        if not approval:
            raise HTTPException(status_code=404, detail="Approval request not found or already reviewed")

        # Update approval record
        await conn.execute(
            """
            UPDATE prompt_approvals
            SET status = 'approved', reviewer = $1, comment = $2, reviewed_at = CURRENT_TIMESTAMP
            WHERE id = $3::uuid
            """,
            user.user_id,
            comment,
            id,
        )

        # Update template status
        await conn.execute(
            """
            UPDATE prompt_templates
            SET status = 'approved', approved_by = $1, approved_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = $2::uuid
            """,
            user.user_id,
            str(approval["template_id"]),
        )

        return {"status": "approved"}


@router.post("/prompt-approvals/{id}/reject")
async def reject_prompt(
    id: str,
    data: Optional[Dict[str, Any]] = None,
    user: UserInfo = Depends(require_admin),
):
    """Reject a prompt template."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    comment = (data or {}).get("comment")

    async with deps.db_pool.acquire() as conn:
        approval = await conn.fetchrow(
            "SELECT * FROM prompt_approvals WHERE id = $1::uuid AND status = 'pending'",
            id,
        )
        if not approval:
            raise HTTPException(status_code=404, detail="Approval request not found or already reviewed")

        # Update approval record
        await conn.execute(
            """
            UPDATE prompt_approvals
            SET status = 'rejected', reviewer = $1, comment = $2, reviewed_at = CURRENT_TIMESTAMP
            WHERE id = $3::uuid
            """,
            user.user_id,
            comment,
            id,
        )

        # Update template status back to draft
        await conn.execute(
            """
            UPDATE prompt_templates
            SET status = 'draft', updated_at = CURRENT_TIMESTAMP
            WHERE id = $1::uuid
            """,
            str(approval["template_id"]),
        )

        return {"status": "rejected"}


@router.get("/prompts/{slug}/analytics")
async def prompt_analytics(slug: str, user: UserInfo = Depends(get_current_user)):
    """Get usage analytics for a prompt template across versions."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        # Get all template IDs for this slug
        templates = await conn.fetch(
            "SELECT id, version FROM prompt_templates WHERE slug = $1 AND is_active = true ORDER BY version",
            slug,
        )
        if not templates:
            raise HTTPException(status_code=404, detail="Prompt template not found")

        template_ids = [row["id"] for row in templates]

        rows = await conn.fetch(
            """
            SELECT
                template_version as version,
                COUNT(*) as total_uses,
                AVG(latency_ms)::numeric as avg_latency_ms,
                SUM(cost)::numeric as total_cost,
                SUM(input_tokens) as total_input_tokens,
                SUM(output_tokens) as total_output_tokens
            FROM prompt_template_usage
            WHERE template_id = ANY($1::uuid[])
            GROUP BY template_version
            ORDER BY template_version
            """,
            template_ids,
        )

        stats = []
        for row in rows:
            stats.append(
                PromptUsageStats(
                    version=row["version"] or 0,
                    total_uses=row["total_uses"],
                    avg_latency_ms=float(row["avg_latency_ms"]) if row["avg_latency_ms"] else None,
                    total_cost=float(row["total_cost"]) if row["total_cost"] else None,
                    total_input_tokens=row["total_input_tokens"],
                    total_output_tokens=row["total_output_tokens"],
                ).model_dump()
            )

        return {
            "slug": slug,
            "versions": [row["version"] for row in templates],
            "usage": stats,
        }
