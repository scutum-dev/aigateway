"""Prompt registry router — template management, versioning, approvals, and analytics."""

import json
import logging
import re
import time
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

import deps
from auth import UserInfo, get_current_user, require_admin
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from routers.deprecations import check_model_deprecation
from routers.dlp import scan_text_with_detectors

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class VariableSpec(BaseModel):
    name: str = Field(..., description="Human-readable template name")
    type: str = "string"
    required: bool = True
    default: Optional[str] = None


class PromptTemplateCreate(BaseModel):
    name: str = Field(..., description="Updated template name")
    slug: str = Field(..., description="URL-friendly unique identifier")
    description: Optional[str] = Field(None, description="Brief description of what this prompt does")
    category: Optional[str] = Field(None, description="Template category for organization")
    template_text: str = Field(..., description="Prompt content with {{variable}} placeholders")
    variables: Optional[List[VariableSpec]] = Field(None, description="Updated variable definitions")
    model_hint: Optional[str] = Field(None, description="Suggested model for execution")
    tags: Optional[List[str]] = Field(None, description="Searchable tags for categorization")


class PromptTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = Field(None, description="Updated description")
    category: Optional[str] = Field(None, description="Updated category")
    template_text: Optional[str] = Field(None, description="Prompt content with {{variable}} placeholders")
    variables: Optional[List[VariableSpec]] = Field(None, description="List of template variable definitions")
    model_hint: Optional[str] = Field(None, description="Updated model suggestion")
    tags: Optional[List[str]] = Field(None, description="Updated tags")
    status: Optional[str] = Field(None, description="Review status (pending, approved, rejected)")


class PromptTemplate(BaseModel):
    id: str = Field(..., description="Unique template identifier (UUID)")
    name: str = Field(..., description="Human-readable template name")
    slug: str = Field(..., description="URL-friendly unique identifier")
    description: Optional[str] = Field(None, description="Brief description of what this prompt does")
    category: Optional[str] = Field(None, description="Template category for organization")
    template_text: str = Field(..., description="Updated prompt content")
    variables: List[Dict[str, Any]] = Field([], description="Variable name-value pairs for substitution")
    version: int = Field(..., description="Auto-incrementing version number")
    is_current: bool = Field(..., description="Whether this is the active version")
    status: str = Field(..., description="Updated status (draft, pending_review, approved)")
    team_id: Optional[str] = Field(None, description="Owning team identifier")
    model_hint: Optional[str] = Field(None, description="Suggested model for execution")
    tags: List[str] = Field([], description="Searchable tags for categorization")
    created_by: Optional[str] = Field(None, description="User who created this version")
    approved_by: Optional[str] = Field(None, description="Admin who approved this version")
    approved_at: Optional[str] = Field(None, description="ISO 8601 approval timestamp")
    is_active: bool = Field(True, description="Whether this template is active (not deleted)")
    created_at: Optional[str] = Field(None, description="ISO 8601 creation timestamp")
    updated_at: Optional[str] = Field(None, description="ISO 8601 last-update timestamp")


class PromptApproval(BaseModel):
    id: str = Field(..., description="Unique approval request identifier (UUID)")
    template_id: str = Field(..., description="Template being reviewed")
    template_version: int = Field(..., description="Version under review")
    requested_by: str = Field(..., description="User who submitted the review")
    reviewer: Optional[str] = Field(None, description="Admin who reviewed the request")
    status: str = Field(..., description="Approval status (draft, pending_review, approved)")
    comment: Optional[str] = Field(None, description="Reviewer comment or feedback")
    requested_at: Optional[str] = Field(None, description="ISO 8601 request timestamp")
    reviewed_at: Optional[str] = Field(None, description="ISO 8601 review timestamp")


class PromptRenderRequest(BaseModel):
    variables: Dict[str, str] = Field({}, description="Variable name-value pairs for substitution")


class PromptExecuteRequest(BaseModel):
    variables: Dict[str, str] = {}
    model: Optional[str] = None  # Override model_hint
    max_tokens: Optional[int] = Field(None, description="Maximum tokens in the LLM response")
    temperature: Optional[float] = Field(None, description="Sampling temperature (0.0 to 2.0)")


class PromptUsageStats(BaseModel):
    version: int = Field(..., description="Template version number")
    total_uses: int = Field(..., description="Total number of executions")
    avg_latency_ms: Optional[float] = Field(None, description="Average execution latency in milliseconds")
    total_cost: Optional[float] = Field(None, description="Cumulative cost in USD")
    total_input_tokens: Optional[int] = Field(None, description="Total prompt tokens consumed")
    total_output_tokens: Optional[int] = Field(None, description="Total completion tokens generated")


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


@router.post("/prompts/{slug}/execute")
async def execute_prompt(
    slug: str,
    data: PromptExecuteRequest,
    user: UserInfo = Depends(get_current_user),
):
    """Render a prompt template and execute it against LiteLLM, tracking usage."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM prompt_templates WHERE slug = $1 AND is_current = true AND is_active = true",
            slug,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Prompt template not found")

        if row["status"] != "approved" and row["status"] != "draft":
            raise HTTPException(
                status_code=400,
                detail=f"Template status is '{row['status']}', must be 'approved' or 'draft'",
            )

        # Render template
        template_text = row["template_text"]
        rendered = template_text
        for key, value in data.variables.items():
            rendered = rendered.replace("{{" + key + "}}", value)

        unresolved = re.findall(r"\{\{(\w+)\}\}", rendered)
        if unresolved:
            raise HTTPException(
                status_code=400,
                detail=f"Unresolved variables: {', '.join(unresolved)}",
            )

        # DLP scan: check rendered text before sending to LLM
        warnings = {}
        dlp_result = await scan_text_with_detectors(
            text=rendered,
            team_id=str(row["team_id"]) if row["team_id"] else None,
        )
        if dlp_result["blocked"]:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Content blocked by DLP policy",
                    "reasons": dlp_result["block_reasons"],
                    "matches": dlp_result["matches"],
                },
            )
        if dlp_result["matches"]:
            warnings["dlp_warnings"] = dlp_result["matches"]

        # Determine model
        model = data.model or row["model_hint"] or "gpt-4o-mini"

        # Deprecation check: warn or block if model is deprecated/sunset
        deprecation = await check_model_deprecation(model)
        if deprecation["sunset"]:
            replacement = deprecation["replacement_model"]
            msg = deprecation["message"] or f"Model '{model}' has been sunset."
            if replacement:
                msg += f" Use '{replacement}' instead."
            raise HTTPException(status_code=410, detail=msg)
        if deprecation["deprecated"]:
            warnings["deprecation_warning"] = {
                "message": deprecation["message"] or f"Model '{model}' is deprecated.",
                "replacement_model": deprecation["replacement_model"],
            }

        # Call LiteLLM
        if not deps.http_client:
            raise HTTPException(status_code=503, detail="HTTP client not available")

        llm_request = {
            "model": model,
            "messages": [{"role": "user", "content": rendered}],
        }
        if data.max_tokens:
            llm_request["max_tokens"] = data.max_tokens
        if data.temperature is not None:
            llm_request["temperature"] = data.temperature

        start_time = time.time()
        try:
            response = await deps.http_client.post(
                f"{deps.LITELLM_URL}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {deps.LITELLM_MASTER_KEY}",
                    "Content-Type": "application/json",
                },
                json=llm_request,
                timeout=120.0,
            )
            response.raise_for_status()
            llm_result = response.json()
        except Exception as e:
            logger.error("LiteLLM call failed for prompt %s: %s", slug, e)
            raise HTTPException(status_code=502, detail=f"LLM request failed: {str(e)}")

        latency_ms = int((time.time() - start_time) * 1000)

        # Extract usage
        usage = llm_result.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        cost = llm_result.get("_hidden_params", {}).get("spend", 0) or 0

        # Record usage
        try:
            await conn.execute(
                """
                INSERT INTO prompt_template_usage
                    (template_id, template_version, user_id, model, input_tokens, output_tokens, cost, latency_ms, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                row["id"],
                row["version"],
                user.user_id,
                model,
                input_tokens,
                output_tokens,
                cost,
                latency_ms,
                "success",
            )
        except Exception as e:
            logger.warning("Failed to record prompt usage: %s", e)

        result = {
            "rendered_prompt": rendered,
            "model": model,
            "response": llm_result.get("choices", [{}])[0].get("message", {}).get("content", ""),
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "latency_ms": latency_ms,
            },
            "template_version": row["version"],
        }
        if warnings:
            result["warnings"] = warnings
        return result


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
