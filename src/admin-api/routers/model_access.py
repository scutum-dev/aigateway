"""Model access governance router — tiers, access requests, and approvals."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import deps
from auth import UserInfo, get_current_user, require_admin
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ModelAccessTierCreate(BaseModel):
    name: str = Field(..., description="Tier display name")
    description: Optional[str] = Field(None, description="Brief description of this access level")
    requires_approval: Optional[bool] = Field(False, description="Whether access requires admin approval")
    requires_justification: Optional[bool] = Field(False, description="Whether users must provide a reason")
    max_grant_duration_days: Optional[int] = Field(None, description="Auto-expiry period in days")
    models: Optional[List[str]] = Field(None, description="Explicit list of allowed models")


class ModelAccessTier(BaseModel):
    id: str = Field(..., description="Unique tier identifier (UUID)")
    name: str = Field(..., description="Tier display name")
    description: Optional[str] = Field(None, description="Brief description of this access level")
    requires_approval: bool = Field(False, description="Whether access requires admin approval")
    requires_justification: bool = Field(False, description="Whether users must provide a reason")
    max_grant_duration_days: Optional[int] = Field(None, description="Auto-expiry period in days")
    models: List[str] = Field(default=[], description="List of allowed models")
    created_at: Optional[str] = Field(None, description="ISO 8601 creation timestamp")


class ModelAccessRequestCreate(BaseModel):
    model_pattern: str = Field(..., description="Model pattern being requested")
    tier_id: Optional[str] = Field(None, description="Access tier being requested")
    team_id: Optional[str] = Field(None, description="Team to grant access to")
    justification: Optional[str] = Field(None, description="Reason for requesting access")


class ModelAccessRequest(BaseModel):
    id: str = Field(..., description="Unique request identifier (UUID)")
    user_id: str = Field(..., description="User who submitted the request")
    team_id: Optional[str] = Field(None, description="Team to grant access to")
    model_pattern: str = Field(..., description="Model pattern being requested")
    tier_id: Optional[str] = Field(None, description="Access tier being requested")
    justification: Optional[str] = Field(None, description="Reason for requesting access")
    status: str = Field("pending", description="Request status (pending, approved, rejected)")
    reviewer: Optional[str] = Field(None, description="Admin who reviewed the request")
    review_comment: Optional[str] = Field(None, description="Reviewer comment or feedback")
    granted_at: Optional[str] = None
    expires_at: Optional[str] = None
    created_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_tier(row) -> ModelAccessTier:
    return ModelAccessTier(
        id=str(row["id"]),
        name=row["name"],
        description=row["description"],
        requires_approval=row["requires_approval"],
        requires_justification=row["requires_justification"],
        max_grant_duration_days=row["max_grant_duration_days"],
        models=list(row["models"]) if row["models"] else [],
        created_at=str(row["created_at"]) if row["created_at"] else None,
    )


def _row_to_request(row) -> ModelAccessRequest:
    return ModelAccessRequest(
        id=str(row["id"]),
        user_id=row["user_id"],
        team_id=str(row["team_id"]) if row["team_id"] else None,
        model_pattern=row["model_pattern"],
        tier_id=str(row["tier_id"]) if row["tier_id"] else None,
        justification=row["justification"],
        status=row["status"],
        reviewer=row["reviewer"],
        review_comment=row["review_comment"],
        granted_at=str(row["granted_at"]) if row["granted_at"] else None,
        expires_at=str(row["expires_at"]) if row["expires_at"] else None,
        created_at=str(row["created_at"]) if row["created_at"] else None,
    )


async def _grant_model_access_in_litellm(team_id: str, model_pattern: str):
    """Add a model to a team's allowed models in LiteLLM."""
    if not deps.http_client or not team_id:
        return

    try:
        headers = {
            "Authorization": f"Bearer {deps.LITELLM_MASTER_KEY}",
            "Content-Type": "application/json",
        }

        # First get the current team info to get existing models
        info_resp = await deps.http_client.get(
            f"{deps.LITELLM_URL}/team/info",
            headers=headers,
            params={"team_id": team_id},
        )

        current_models = []
        if info_resp.status_code == 200:
            team_info = info_resp.json().get("team_info", {})
            current_models = team_info.get("models", []) or []

        # Add the new model if not already present
        if model_pattern not in current_models:
            current_models.append(model_pattern)

            resp = await deps.http_client.post(
                f"{deps.LITELLM_URL}/team/update",
                headers=headers,
                json={
                    "team_id": team_id,
                    "models": current_models,
                },
            )
            if resp.status_code == 200:
                logger.info("Granted model %s to team %s in LiteLLM", model_pattern, team_id)
            else:
                logger.warning("LiteLLM /team/update returned %s: %s", resp.status_code, resp.text[:200])
        else:
            logger.info("Model %s already in team %s models", model_pattern, team_id)
    except Exception as e:
        logger.warning("Failed to grant model access in LiteLLM: %s", e)


async def _revoke_model_access_in_litellm(team_id: str, model_pattern: str):
    """Remove a model from a team's allowed models in LiteLLM (for expiry)."""
    if not deps.http_client or not team_id:
        return

    try:
        headers = {
            "Authorization": f"Bearer {deps.LITELLM_MASTER_KEY}",
            "Content-Type": "application/json",
        }

        info_resp = await deps.http_client.get(
            f"{deps.LITELLM_URL}/team/info",
            headers=headers,
            params={"team_id": team_id},
        )

        if info_resp.status_code == 200:
            team_info = info_resp.json().get("team_info", {})
            current_models = team_info.get("models", []) or []

            if model_pattern in current_models:
                current_models.remove(model_pattern)
                await deps.http_client.post(
                    f"{deps.LITELLM_URL}/team/update",
                    headers=headers,
                    json={
                        "team_id": team_id,
                        "models": current_models,
                    },
                )
                logger.info("Revoked model %s from team %s in LiteLLM", model_pattern, team_id)
    except Exception as e:
        logger.warning("Failed to revoke model access in LiteLLM: %s", e)


# ---------------------------------------------------------------------------
# Tier Endpoints
# ---------------------------------------------------------------------------


@router.get("/model-access/tiers", response_model=List[ModelAccessTier])
async def list_tiers(user: UserInfo = Depends(get_current_user)):
    """List all model access tiers."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM model_access_tiers ORDER BY name")
        return [_row_to_tier(row) for row in rows]


@router.post("/model-access/tiers", response_model=ModelAccessTier)
async def create_tier(
    data: ModelAccessTierCreate,
    user: UserInfo = Depends(require_admin),
):
    """Create a model access tier."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO model_access_tiers (name, description, requires_approval, requires_justification, max_grant_duration_days, models)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *
            """,
            data.name,
            data.description,
            data.requires_approval or False,
            data.requires_justification or False,
            data.max_grant_duration_days,
            data.models or [],
        )
        return _row_to_tier(row)


@router.put("/model-access/tiers/{id}", response_model=ModelAccessTier)
async def update_tier(
    id: str,
    data: ModelAccessTierCreate,
    user: UserInfo = Depends(require_admin),
):
    """Update a model access tier."""
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
    if data.requires_approval is not None:
        sets.append(f"requires_approval = ${idx}")
        params.append(data.requires_approval)
        idx += 1
    if data.requires_justification is not None:
        sets.append(f"requires_justification = ${idx}")
        params.append(data.requires_justification)
        idx += 1
    if data.max_grant_duration_days is not None:
        sets.append(f"max_grant_duration_days = ${idx}")
        params.append(data.max_grant_duration_days)
        idx += 1
    if data.models is not None:
        sets.append(f"models = ${idx}")
        params.append(data.models)
        idx += 1

    if not sets:
        raise HTTPException(status_code=400, detail="No fields to update")

    params.append(id)
    query = f"""
        UPDATE model_access_tiers SET {", ".join(sets)}
        WHERE id = ${idx}::uuid
        RETURNING *
    """

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(query, *params)
        if not row:
            raise HTTPException(status_code=404, detail="Tier not found")
        return _row_to_tier(row)


@router.delete("/model-access/tiers/{id}")
async def delete_tier(id: str, user: UserInfo = Depends(require_admin)):
    """Delete a model access tier."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        result = await conn.execute("DELETE FROM model_access_tiers WHERE id = $1::uuid", id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Tier not found")
        return {"status": "ok"}


# ---------------------------------------------------------------------------
# Access Request Endpoints
# ---------------------------------------------------------------------------


@router.post("/model-access/requests", response_model=ModelAccessRequest)
async def create_request(
    data: ModelAccessRequestCreate,
    user: UserInfo = Depends(get_current_user),
):
    """Submit a model access request."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        # If tier_id provided, check if tier requires justification
        if data.tier_id:
            tier = await conn.fetchrow(
                "SELECT * FROM model_access_tiers WHERE id = $1::uuid",
                data.tier_id,
            )
            if not tier:
                raise HTTPException(status_code=404, detail="Tier not found")
            if tier["requires_justification"] and not data.justification:
                raise HTTPException(status_code=400, detail="Justification is required for this tier")

            # Auto-approve if tier does not require approval
            status = "pending" if tier["requires_approval"] else "approved"
            granted_at = None if tier["requires_approval"] else datetime.now(timezone.utc)
            expires_at = None
            if not tier["requires_approval"] and tier["max_grant_duration_days"]:
                expires_at = datetime.now(timezone.utc) + timedelta(days=tier["max_grant_duration_days"])
        else:
            status = "pending"
            granted_at = None
            expires_at = None

        row = await conn.fetchrow(
            """
            INSERT INTO model_access_requests (user_id, team_id, model_pattern, tier_id, justification, status, granted_at, expires_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *
            """,
            user.user_id,
            data.team_id,
            data.model_pattern,
            data.tier_id,
            data.justification,
            status,
            granted_at,
            expires_at,
        )
        return _row_to_request(row)


@router.get("/model-access/requests", response_model=List[ModelAccessRequest])
async def list_requests(
    status: Optional[str] = Query(default=None),
    user: UserInfo = Depends(get_current_user),
):
    """List access requests. Admins see all, regular users see only their own."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    conditions: list = []
    params: list = []
    idx = 1

    # Non-admin users only see their own requests
    if user.role != "admin":
        conditions.append(f"user_id = ${idx}")
        params.append(user.user_id)
        idx += 1

    if status:
        conditions.append(f"status = ${idx}")
        params.append(status)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"SELECT * FROM model_access_requests {where} ORDER BY created_at DESC"

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        return [_row_to_request(row) for row in rows]


@router.post("/model-access/requests/{id}/approve")
async def approve_request(
    id: str,
    data: Optional[Dict[str, Any]] = None,
    user: UserInfo = Depends(require_admin),
):
    """Approve a model access request."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    comment = (data or {}).get("comment")

    async with deps.db_pool.acquire() as conn:
        request = await conn.fetchrow(
            "SELECT * FROM model_access_requests WHERE id = $1::uuid AND status = 'pending'",
            id,
        )
        if not request:
            raise HTTPException(status_code=404, detail="Access request not found or already reviewed")

        # Calculate expiry if tier has max_grant_duration_days
        expires_at = None
        if request["tier_id"]:
            tier = await conn.fetchrow(
                "SELECT max_grant_duration_days FROM model_access_tiers WHERE id = $1::uuid",
                request["tier_id"],
            )
            if tier and tier["max_grant_duration_days"]:
                expires_at = datetime.now(timezone.utc) + timedelta(days=tier["max_grant_duration_days"])

        await conn.execute(
            """
            UPDATE model_access_requests
            SET status = 'approved', reviewer = $1, review_comment = $2, granted_at = CURRENT_TIMESTAMP, expires_at = $3
            WHERE id = $4::uuid
            """,
            user.user_id,
            comment,
            expires_at,
            id,
        )

        # Grant model access in LiteLLM
        if request["team_id"]:
            await _grant_model_access_in_litellm(
                str(request["team_id"]),
                request["model_pattern"],
            )

        return {"status": "approved"}


@router.post("/model-access/requests/{id}/reject")
async def reject_request(
    id: str,
    data: Optional[Dict[str, Any]] = None,
    user: UserInfo = Depends(require_admin),
):
    """Reject a model access request."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    comment = (data or {}).get("comment")

    async with deps.db_pool.acquire() as conn:
        request = await conn.fetchrow(
            "SELECT * FROM model_access_requests WHERE id = $1::uuid AND status = 'pending'",
            id,
        )
        if not request:
            raise HTTPException(status_code=404, detail="Access request not found or already reviewed")

        await conn.execute(
            """
            UPDATE model_access_requests
            SET status = 'rejected', reviewer = $1, review_comment = $2
            WHERE id = $3::uuid
            """,
            user.user_id,
            comment,
            id,
        )
        return {"status": "rejected"}


@router.get("/model-access/my-access", response_model=List[ModelAccessRequest])
async def my_access(user: UserInfo = Depends(get_current_user)):
    """Get the current user's active model access grants."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM model_access_requests
            WHERE user_id = $1
              AND status = 'approved'
              AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            ORDER BY granted_at DESC
            """,
            user.user_id,
        )
        return [_row_to_request(row) for row in rows]
