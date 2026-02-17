import json
from datetime import datetime, timezone
from typing import Optional

import state
from a2a_models import Agent, AgentStatus
from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["Agents"])


@router.post("/agents/register")
async def register_agent(agent: Agent):
    """Register an agent in the registry."""
    agent.registered_at = datetime.now(timezone.utc).isoformat()
    agent.last_heartbeat = agent.registered_at

    await state.redis_client.hset("a2a:agents", agent.id, agent.model_dump_json())

    # Index capabilities
    for cap in agent.capabilities:
        await state.redis_client.sadd(f"a2a:capabilities:{cap.name}", agent.id)

    return {"status": "registered", "agent_id": agent.id}


@router.delete("/agents/{agent_id}")
async def unregister_agent(agent_id: str):
    """Unregister an agent."""
    agent_data = await state.redis_client.hget("a2a:agents", agent_id)
    if agent_data:
        agent = Agent(**json.loads(agent_data))
        for cap in agent.capabilities:
            await state.redis_client.srem(f"a2a:capabilities:{cap.name}", agent_id)

    await state.redis_client.hdel("a2a:agents", agent_id)
    return {"status": "unregistered", "agent_id": agent_id}


@router.post("/agents/{agent_id}/heartbeat")
async def agent_heartbeat(agent_id: str):
    """Update agent heartbeat."""
    agent_data = await state.redis_client.hget("a2a:agents", agent_id)
    if not agent_data:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent = Agent(**json.loads(agent_data))
    agent.last_heartbeat = datetime.now(timezone.utc).isoformat()
    agent.status = AgentStatus.AVAILABLE

    await state.redis_client.hset("a2a:agents", agent_id, agent.model_dump_json())
    return {"status": "ok"}


@router.get("/agents")
async def list_agents(capability: Optional[str] = None):
    """List registered agents."""
    if capability:
        agent_ids = await state.redis_client.smembers(f"a2a:capabilities:{capability}")
        agents = []
        for agent_id in agent_ids:
            data = await state.redis_client.hget("a2a:agents", agent_id)
            if data:
                agents.append(json.loads(data))
        return {"agents": agents}

    all_agents = await state.redis_client.hgetall("a2a:agents")
    return {"agents": [json.loads(v) for v in all_agents.values()]}


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Get agent details."""
    data = await state.redis_client.hget("a2a:agents", agent_id)
    if not data:
        raise HTTPException(status_code=404, detail="Agent not found")
    return json.loads(data)


@router.get("/capabilities")
async def list_capabilities():
    """List all available capabilities."""
    capabilities = {}
    async for key in state.redis_client.scan_iter(match="a2a:capabilities:*"):
        cap_name = key.split(":")[-1]
        agent_ids = await state.redis_client.smembers(key)
        capabilities[cap_name] = list(agent_ids)
    return {"capabilities": capabilities}
