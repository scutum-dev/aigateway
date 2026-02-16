import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter
import httpx

import state
from a2a_models import Agent, AgentMessage

router = APIRouter(tags=["Messages"])


@router.post("/messages")
async def send_agent_message(message: AgentMessage):
    """Send a message between agents."""
    message.id = str(uuid.uuid4())
    message.created_at = datetime.now(timezone.utc).isoformat()

    # Store message
    await state.redis_client.rpush(
        f"a2a:messages:{message.target_agent}",
        message.model_dump_json(),
    )

    # Notify target agent (best effort)
    try:
        agent_data = await state.redis_client.hget("a2a:agents", message.target_agent)
        if agent_data:
            agent = Agent(**json.loads(agent_data))
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(f"{agent.endpoint}/messages/notify", json={"message_id": message.id})
    except Exception:
        pass

    return {"status": "sent", "message_id": message.id}


@router.get("/messages/{agent_id}")
async def get_agent_messages(agent_id: str, limit: int = 100):
    """Get messages for an agent."""
    messages = await state.redis_client.lrange(f"a2a:messages:{agent_id}", 0, limit - 1)
    return {"messages": [json.loads(m) for m in messages]}
