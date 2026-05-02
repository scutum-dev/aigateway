"""SRE agent proxy router.

The admin UI talks to admin-api on a single origin; this router forwards
SRE incident calls to the sre-agent service. Approval/reject endpoints
attach the calling admin user as the approver and write an audit log entry.
"""

import logging
import os
from typing import Any, Dict, List, Optional

import deps
from audit import log_audit_event
from auth import UserInfo, get_current_user, require_admin
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()

SRE_AGENT_URL = os.getenv("SRE_AGENT_URL", "http://sre-agent:8092").rstrip("/")
INTERNAL_SERVICE_KEY = os.getenv("INTERNAL_SERVICE_KEY", "")


class TriggerRequest(BaseModel):
    event_type: str = Field(..., description="Event type to inject as if it had been published.")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Event payload.")


class RejectRequest(BaseModel):
    reason: Optional[str] = Field(None, description="Free-text reason for rejection.")


def _service_headers() -> Dict[str, str]:
    return {"X-Service-Key": INTERNAL_SERVICE_KEY} if INTERNAL_SERVICE_KEY else {}


@router.get("/sre/incidents")
async def list_incidents(
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    user: UserInfo = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    if not deps.http_client:
        raise HTTPException(status_code=503, detail="HTTP client not initialized")
    params = {"limit": limit}
    if status:
        params["status"] = status
    try:
        resp = await deps.http_client.get(
            f"{SRE_AGENT_URL}/incidents", params=params, headers=_service_headers(), timeout=10.0
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"sre-agent unreachable: {e}")
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@router.get("/sre/incidents/{incident_id}")
async def get_incident(incident_id: str, user: UserInfo = Depends(get_current_user)) -> Dict[str, Any]:
    if not deps.http_client:
        raise HTTPException(status_code=503, detail="HTTP client not initialized")
    try:
        resp = await deps.http_client.get(
            f"{SRE_AGENT_URL}/incidents/{incident_id}", headers=_service_headers(), timeout=10.0
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"sre-agent unreachable: {e}")
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Incident not found")
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@router.post("/sre/incidents/{incident_id}/approve")
async def approve_incident(
    incident_id: str,
    request: Request,
    user: UserInfo = Depends(require_admin),
) -> Dict[str, Any]:
    """Approve an incident's proposed plan and execute it via the SRE agent."""
    if not deps.http_client:
        raise HTTPException(status_code=503, detail="HTTP client not initialized")
    try:
        resp = await deps.http_client.post(
            f"{SRE_AGENT_URL}/incidents/{incident_id}/execute",
            json={"approver": user.user_id},
            headers=_service_headers(),
            timeout=60.0,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"sre-agent unreachable: {e}")
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    body = resp.json()
    await log_audit_event(
        actor_id=user.user_id,
        actor_email=user.email,
        action="approve",
        resource_type="sre_incident",
        resource_id=incident_id,
        changes={"status": body.get("status"), "executed": body.get("executed")},
        request=request,
    )
    return body


@router.post("/sre/incidents/{incident_id}/reject")
async def reject_incident(
    incident_id: str,
    body: RejectRequest,
    request: Request,
    user: UserInfo = Depends(require_admin),
) -> Dict[str, Any]:
    if not deps.http_client:
        raise HTTPException(status_code=503, detail="HTTP client not initialized")
    try:
        resp = await deps.http_client.post(
            f"{SRE_AGENT_URL}/incidents/{incident_id}/reject",
            json={"approver": user.user_id, "reason": body.reason},
            headers=_service_headers(),
            timeout=10.0,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"sre-agent unreachable: {e}")
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    result = resp.json()
    await log_audit_event(
        actor_id=user.user_id,
        actor_email=user.email,
        action="reject",
        resource_type="sre_incident",
        resource_id=incident_id,
        changes={"reason": body.reason},
        request=request,
    )
    return result


@router.post("/sre/trigger")
async def manual_trigger(
    body: TriggerRequest,
    request: Request,
    user: UserInfo = Depends(require_admin),
) -> Dict[str, Any]:
    """Manually open an incident — bypasses event_publisher and goes straight to sre-agent."""
    if not deps.http_client:
        raise HTTPException(status_code=503, detail="HTTP client not initialized")
    try:
        resp = await deps.http_client.post(
            f"{SRE_AGENT_URL}/trigger",
            json={"event_type": body.event_type, "payload": body.payload},
            headers=_service_headers(),
            timeout=10.0,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"sre-agent unreachable: {e}")
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    result = resp.json()
    await log_audit_event(
        actor_id=user.user_id,
        actor_email=user.email,
        action="manual_trigger",
        resource_type="sre_incident",
        resource_id=result.get("incident_id"),
        changes={"event_type": body.event_type, "payload": body.payload},
        request=request,
    )
    return result


@router.get("/sre/stats")
async def stats(user: UserInfo = Depends(get_current_user)) -> Dict[str, Any]:
    if not deps.http_client:
        raise HTTPException(status_code=503, detail="HTTP client not initialized")
    try:
        resp = await deps.http_client.get(f"{SRE_AGENT_URL}/stats", headers=_service_headers(), timeout=10.0)
    except Exception as e:
        # Stats are nice-to-have; degrade gracefully if the agent is down.
        return {"by_status": {}, "mttr_seconds": None, "agent_reachable": False, "error": str(e)}
    if resp.status_code != 200:
        return {"by_status": {}, "mttr_seconds": None, "agent_reachable": False, "error": resp.text}
    body = resp.json()
    body["agent_reachable"] = True
    return body
