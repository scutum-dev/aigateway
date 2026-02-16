import json
from datetime import datetime, timezone

from fastapi import APIRouter

import state
from a2a_models import HumanApprovalRequest

router = APIRouter(tags=["Approvals"])


@router.post("/approvals")
async def submit_approval(approval: HumanApprovalRequest):
    """Submit human approval for a workflow step."""
    key = f"a2a:approvals:{approval.workflow_id}:{approval.step_id}"
    await state.redis_client.set(
        key,
        json.dumps({
            "approved": approval.approved,
            "comment": approval.comment,
            "approver": approval.approver,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }),
        ex=86400,  # 24 hour expiry
    )
    return {"status": "submitted"}


@router.get("/approvals/pending")
async def list_pending_approvals():
    """List pending human approvals."""
    pending = []
    async for key in state.redis_client.scan_iter(match="a2a:approvals:*:*"):
        data = await state.redis_client.get(key)
        if not data:
            parts = key.split(":")
            pending.append({
                "workflow_id": parts[2],
                "step_id": parts[3],
            })
    return {"pending": pending}
