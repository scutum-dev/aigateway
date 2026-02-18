"""Audit log viewer router."""

import csv
import io
import json
from typing import List, Optional

import deps
from auth import UserInfo, get_current_user, require_admin
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class AuditLogEntry(BaseModel):
    id: str = Field(..., description="Unique audit log entry identifier (UUID)")
    timestamp: Optional[str] = Field(None, description="ISO 8601 event timestamp")
    actor_id: str = Field(..., description="User ID who performed the action")
    actor_email: Optional[str] = Field(None, description="Email of the actor")
    actor_ip: Optional[str] = Field(None, description="IP address of the actor")
    org_id: Optional[str] = Field(None, description="Organization context (UUID)")
    action: str = Field(..., description="Action performed (create, update, delete)")
    resource_type: str = Field(..., description="Type of resource affected")
    resource_id: Optional[str] = Field(None, description="Identifier of the affected resource")
    resource_name: Optional[str] = Field(None, description="Human-readable name of the resource")
    changes: dict = Field({}, description="JSON diff of changes made")
    request_metadata: dict = Field({}, description="HTTP request metadata (method, path, user-agent)")
    created_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_entry(row) -> AuditLogEntry:
    changes = row["changes"]
    if isinstance(changes, str):
        changes = json.loads(changes)
    req_meta = row["request_metadata"]
    if isinstance(req_meta, str):
        req_meta = json.loads(req_meta)
    return AuditLogEntry(
        id=str(row["id"]),
        timestamp=str(row["timestamp"]) if row["timestamp"] else None,
        actor_id=row["actor_id"],
        actor_email=row["actor_email"],
        actor_ip=row["actor_ip"],
        org_id=str(row["org_id"]) if row["org_id"] else None,
        action=row["action"],
        resource_type=row["resource_type"],
        resource_id=row["resource_id"],
        resource_name=row["resource_name"],
        changes=changes if isinstance(changes, dict) else {},
        request_metadata=req_meta if isinstance(req_meta, dict) else {},
        created_at=str(row["created_at"]) if row["created_at"] else None,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/audit-logs", response_model=List[AuditLogEntry])
async def list_audit_logs(
    actor_id: Optional[str] = Query(default=None),
    resource_type: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    org_id: Optional[str] = Query(default=None),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    user: UserInfo = Depends(get_current_user),
):
    """List audit logs with filters."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    conditions = []
    params: list = []
    idx = 1

    if actor_id:
        conditions.append(f"actor_id = ${idx}")
        params.append(actor_id)
        idx += 1
    if resource_type:
        conditions.append(f"resource_type = ${idx}")
        params.append(resource_type)
        idx += 1
    if action:
        conditions.append(f"action = ${idx}")
        params.append(action)
        idx += 1
    if org_id:
        conditions.append(f"org_id = ${idx}::uuid")
        params.append(org_id)
        idx += 1
    if start_date:
        conditions.append(f"timestamp >= ${idx}::timestamptz")
        params.append(start_date)
        idx += 1
    if end_date:
        conditions.append(f"timestamp <= ${idx}::timestamptz")
        params.append(end_date)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    params.append(limit)
    params.append(offset)

    query = f"""
        SELECT * FROM audit_logs
        {where}
        ORDER BY timestamp DESC
        LIMIT ${idx} OFFSET ${idx + 1}
    """

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        return [_row_to_entry(row) for row in rows]


@router.get("/audit-logs/export")
async def export_audit_logs(
    format: str = Query(default="csv"),
    actor_id: Optional[str] = Query(default=None),
    resource_type: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    org_id: Optional[str] = Query(default=None),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    limit: int = Query(default=10000, le=50000),
    user: UserInfo = Depends(require_admin),
):
    """Export audit logs as CSV or JSON."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    conditions = []
    params: list = []
    idx = 1

    if actor_id:
        conditions.append(f"actor_id = ${idx}")
        params.append(actor_id)
        idx += 1
    if resource_type:
        conditions.append(f"resource_type = ${idx}")
        params.append(resource_type)
        idx += 1
    if action:
        conditions.append(f"action = ${idx}")
        params.append(action)
        idx += 1
    if org_id:
        conditions.append(f"org_id = ${idx}::uuid")
        params.append(org_id)
        idx += 1
    if start_date:
        conditions.append(f"timestamp >= ${idx}::timestamptz")
        params.append(start_date)
        idx += 1
    if end_date:
        conditions.append(f"timestamp <= ${idx}::timestamptz")
        params.append(end_date)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    query = f"""
        SELECT * FROM audit_logs
        {where}
        ORDER BY timestamp DESC
        LIMIT ${idx}
    """

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    entries = [_row_to_entry(row) for row in rows]

    if format == "json":
        content = json.dumps([e.model_dump() for e in entries], indent=2, default=str)
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=audit_logs.json"},
        )

    # CSV export
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "timestamp",
            "actor_id",
            "actor_email",
            "actor_ip",
            "org_id",
            "action",
            "resource_type",
            "resource_id",
            "resource_name",
            "changes",
        ]
    )
    for e in entries:
        writer.writerow(
            [
                e.id,
                e.timestamp,
                e.actor_id,
                e.actor_email,
                e.actor_ip,
                e.org_id,
                e.action,
                e.resource_type,
                e.resource_id,
                e.resource_name,
                json.dumps(e.changes),
            ]
        )

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_logs.csv"},
    )
