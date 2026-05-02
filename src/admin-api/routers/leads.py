"""Leads router: read + manage demo_requests rows from the admin UI."""

import json
import logging
from typing import Any, Dict, List, Optional

import deps
from audit import log_audit_event
from auth import UserInfo, get_current_user, require_admin
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()


VALID_STATUSES = {"new", "scheduled", "contacted", "closed"}


class LeadUpdate(BaseModel):
    status: Optional[str] = Field(None, description="One of: new, scheduled, contacted, closed")
    notes: Optional[str] = Field(None, description="Free-text notes appended by the operator")


def _row_to_lead(row) -> Dict[str, Any]:
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "work_email": row["work_email"],
        "company": row["company"],
        "role": row["role"],
        "team_size": row["team_size"],
        "use_case": row["use_case"],
        "preferred_window": (
            json.loads(row["preferred_window"]) if isinstance(row["preferred_window"], str) else row["preferred_window"]
        ),
        "calcom_booking_id": row["calcom_booking_id"],
        "calcom_meeting_url": row["calcom_meeting_url"],
        "source_ip": row["source_ip"],
        "user_agent": row["user_agent"],
        "status": row["status"],
        "notes": row["notes"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


@router.get("/leads")
async def list_leads(
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    user: UserInfo = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    async with deps.db_pool.acquire() as conn:
        if status:
            rows = await conn.fetch(
                "SELECT * FROM demo_requests WHERE status = $1 ORDER BY created_at DESC LIMIT $2",
                status,
                limit,
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM demo_requests ORDER BY created_at DESC LIMIT $1",
                limit,
            )
    return [_row_to_lead(r) for r in rows]


@router.get("/leads/{lead_id}")
async def get_lead(lead_id: str, user: UserInfo = Depends(get_current_user)) -> Dict[str, Any]:
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM demo_requests WHERE id = $1::uuid", lead_id)
        if not row:
            raise HTTPException(status_code=404, detail="Lead not found")
    return _row_to_lead(row)


@router.patch("/leads/{lead_id}")
async def update_lead(
    lead_id: str,
    body: LeadUpdate,
    request: Request,
    user: UserInfo = Depends(require_admin),
) -> Dict[str, Any]:
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    if body.status is not None and body.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {sorted(VALID_STATUSES)}",
        )

    sets: list = []
    params: list = []
    idx = 1
    if body.status is not None:
        sets.append(f"status = ${idx}")
        params.append(body.status)
        idx += 1
    if body.notes is not None:
        sets.append(f"notes = ${idx}")
        params.append(body.notes)
        idx += 1
    if not sets:
        raise HTTPException(status_code=400, detail="No fields to update")
    params.append(lead_id)
    query = f"UPDATE demo_requests SET {', '.join(sets)} WHERE id = ${idx}::uuid RETURNING *"

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(query, *params)
        if not row:
            raise HTTPException(status_code=404, detail="Lead not found")

    await log_audit_event(
        actor_id=user.user_id,
        actor_email=user.email,
        action="update",
        resource_type="lead",
        resource_id=lead_id,
        changes=body.model_dump(exclude_none=True),
        request=request,
    )
    return _row_to_lead(row)
