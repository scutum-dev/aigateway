"""Audit trail utility for logging administrative actions."""

import json
import logging
from typing import Optional

import deps
from fastapi import Request

logger = logging.getLogger(__name__)


async def log_audit_event(
    actor_id: str,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    resource_name: Optional[str] = None,
    changes: Optional[dict] = None,
    request: Optional[Request] = None,
    org_id: Optional[str] = None,
    actor_email: Optional[str] = None,
):
    """Fire-and-forget audit log insert."""
    if not deps.db_pool:
        return
    try:
        actor_ip = None
        request_metadata = {}
        if request:
            actor_ip = request.client.host if request.client else None
            request_metadata = {
                "method": request.method,
                "path": str(request.url.path),
                "user_agent": request.headers.get("user-agent", ""),
            }
        async with deps.db_pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO audit_logs (actor_id, actor_email, actor_ip, org_id, action, resource_type, resource_id, resource_name, changes, request_metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
                actor_id,
                actor_email,
                actor_ip,
                org_id,
                action,
                resource_type,
                resource_id,
                resource_name,
                json.dumps(changes or {}),
                json.dumps(request_metadata),
            )
    except Exception as e:
        logger.warning(f"Failed to write audit log: {e}")
