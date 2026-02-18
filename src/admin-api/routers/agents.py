import json
from typing import List

import deps
import httpx
from auth import UserInfo, get_current_user, require_admin
from fastapi import APIRouter, Depends, HTTPException
from models import A2AAgentConfig, A2AAgentCreate, A2AAgentUpdate

router = APIRouter()


def _row_to_agent(row) -> A2AAgentConfig:
    """Convert database row to A2AAgentConfig."""
    skills = row["skills"] or []
    if isinstance(skills, str):
        try:
            skills = json.loads(skills)
        except (json.JSONDecodeError, TypeError):
            skills = []
    return A2AAgentConfig(
        id=str(row["id"]),
        name=row["name"],
        description=row["description"],
        url=row["url"],
        skills=skills,
        is_active=row["is_active"],
    )


@router.get("/agents", response_model=List[A2AAgentConfig])
async def list_agents(user: UserInfo = Depends(get_current_user)):
    """List all A2A agent configurations."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM a2a_agents ORDER BY name")
        return [_row_to_agent(row) for row in rows]


@router.post("/agents", response_model=A2AAgentConfig)
async def create_agent(agent: A2AAgentCreate, user: UserInfo = Depends(require_admin)):
    """Create a new A2A agent configuration."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO a2a_agents (name, description, url, skills)
            VALUES ($1, $2, $3, $4)
            RETURNING *
        """,
            agent.name,
            agent.description,
            agent.url,
            json.dumps(agent.skills),
        )

        return _row_to_agent(row)


@router.get("/agents/{agent_id}", response_model=A2AAgentConfig)
async def get_agent(agent_id: str, user: UserInfo = Depends(get_current_user)):
    """Get a single A2A agent configuration."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM a2a_agents WHERE id = $1", agent_id)
        if not row:
            raise HTTPException(status_code=404, detail="A2A agent not found")
        return _row_to_agent(row)


@router.put("/agents/{agent_id}", response_model=A2AAgentConfig)
async def update_agent(agent_id: str, update: A2AAgentUpdate, user: UserInfo = Depends(require_admin)):
    """Update an A2A agent configuration."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    updates = []
    params = []
    param_idx = 1

    for field, value in update.model_dump(exclude_unset=True).items():
        if value is not None:
            if field == "skills":
                updates.append(f"{field} = ${param_idx}")
                params.append(json.dumps(value))
            else:
                updates.append(f"{field} = ${param_idx}")
                params.append(value)
            param_idx += 1

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    params.append(agent_id)

    async with deps.db_pool.acquire() as conn:
        query = f"UPDATE a2a_agents SET {', '.join(updates)} WHERE id = ${param_idx} RETURNING *"
        row = await conn.fetchrow(query, *params)

        if not row:
            raise HTTPException(status_code=404, detail="A2A agent not found")

        return _row_to_agent(row)


@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str, user: UserInfo = Depends(require_admin)):
    """Delete an A2A agent configuration."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        result = await conn.execute("DELETE FROM a2a_agents WHERE id = $1", agent_id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="A2A agent not found")

    return {"status": "deleted"}


@router.post("/agents/{agent_id}/test")
async def test_agent(agent_id: str, user: UserInfo = Depends(get_current_user)):
    """Test connectivity to an A2A agent."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM a2a_agents WHERE id = $1", agent_id)
        if not row:
            raise HTTPException(status_code=404, detail="A2A agent not found")

    url = row["url"]
    if not url:
        return {"status": "error", "message": "No URL configured"}
    try:
        response = await deps.http_client.get(url, timeout=5.0)
        return {"status": "ok", "message": f"Reachable — HTTP {response.status_code}"}
    except httpx.ConnectError:
        return {"status": "error", "message": f"Cannot connect to {url}"}
    except httpx.TimeoutException:
        return {"status": "error", "message": f"Timeout connecting to {url}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
