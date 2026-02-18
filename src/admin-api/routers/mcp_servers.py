import json
from typing import List

import deps
import httpx
from auth import UserInfo, get_current_user, require_admin
from fastapi import APIRouter, Depends, HTTPException
from gateway_sync import build_gateway_config, restart_gateway, sync_configmap
from models import MCPServerConfig, MCPServerCreate, MCPServerUpdate

router = APIRouter()


def _parse_env(val) -> dict:
    """Parse env field which may be a dict (jsonb) or a JSON string."""
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _row_to_mcp(row) -> MCPServerConfig:
    """Convert database row to MCPServerConfig."""
    return MCPServerConfig(
        id=str(row["id"]),
        name=row["name"],
        server_type=row["server_type"],
        command=row["command"],
        url=row["url"],
        args=row["args"] or [],
        env=_parse_env(row["env"]),
        tools=row["tools"] or [],
        is_active=row["is_active"],
    )


@router.get("/mcp-servers", response_model=List[MCPServerConfig])
async def list_mcp_servers(user: UserInfo = Depends(get_current_user)):
    """List all MCP server configurations."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM mcp_servers ORDER BY name")
        return [_row_to_mcp(row) for row in rows]


@router.post("/mcp-servers", response_model=MCPServerConfig)
async def create_mcp_server(server: MCPServerCreate, user: UserInfo = Depends(require_admin)):
    """Create a new MCP server configuration."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO mcp_servers (name, server_type, command, url, args, env)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *
        """,
            server.name,
            server.server_type,
            server.command,
            server.url,
            server.args,
            json.dumps(server.env),
        )

        return _row_to_mcp(row)


@router.get("/mcp-servers/sync/preview")
async def preview_gateway_config(user: UserInfo = Depends(get_current_user)):
    """Preview the Agent Gateway config that would be deployed."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM mcp_servers WHERE is_active = true ORDER BY name")
        servers = [
            {
                "name": row["name"],
                "server_type": row["server_type"],
                "command": row["command"],
                "url": row["url"],
                "args": row["args"] or [],
                "env": _parse_env(row["env"]),
            }
            for row in rows
        ]

        agent_rows = await conn.fetch("SELECT * FROM a2a_agents WHERE is_active = true ORDER BY name")
        agents = [{"name": r["name"], "url": r["url"]} for r in agent_rows]

    config_yaml = build_gateway_config(servers, agents)
    return {
        "active_servers": len(servers),
        "active_agents": len(agents),
        "config_yaml": config_yaml,
    }


@router.post("/mcp-servers/sync")
async def sync_mcp_to_gateway(user: UserInfo = Depends(require_admin)):
    """Deploy active MCP server and A2A agent configs to the Agent Gateway."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM mcp_servers WHERE is_active = true ORDER BY name")
        servers = [
            {
                "name": row["name"],
                "server_type": row["server_type"],
                "command": row["command"],
                "url": row["url"],
                "args": row["args"] or [],
                "env": _parse_env(row["env"]),
            }
            for row in rows
        ]

        agent_rows = await conn.fetch("SELECT * FROM a2a_agents WHERE is_active = true ORDER BY name")
        agents = [{"name": r["name"], "url": r["url"]} for r in agent_rows]

    cm_result = await sync_configmap(servers, agents)
    if cm_result["status"] == "error":
        return {
            "status": "error",
            "servers_synced": len(servers),
            "configmap": cm_result,
            "restart": {"status": "skipped"},
        }

    restart_result = await restart_gateway()

    return {
        "status": "ok" if restart_result["status"] == "ok" else "partial",
        "servers_synced": len(servers),
        "configmap": cm_result,
        "restart": restart_result,
    }


@router.put("/mcp-servers/{server_id}", response_model=MCPServerConfig)
async def update_mcp_server(server_id: str, update: MCPServerUpdate, user: UserInfo = Depends(require_admin)):
    """Update an MCP server configuration."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    updates = []
    params = []
    param_idx = 1

    for field, value in update.model_dump(exclude_unset=True).items():
        if value is not None:
            if field == "env":
                updates.append(f"{field} = ${param_idx}")
                params.append(json.dumps(value))
            else:
                updates.append(f"{field} = ${param_idx}")
                params.append(value)
            param_idx += 1

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    params.append(server_id)

    async with deps.db_pool.acquire() as conn:
        query = f"UPDATE mcp_servers SET {', '.join(updates)} WHERE id = ${param_idx} RETURNING *"
        row = await conn.fetchrow(query, *params)

        if not row:
            raise HTTPException(status_code=404, detail="MCP server not found")

        return _row_to_mcp(row)


@router.delete("/mcp-servers/{server_id}")
async def delete_mcp_server(server_id: str, user: UserInfo = Depends(require_admin)):
    """Delete an MCP server configuration."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        result = await conn.execute("DELETE FROM mcp_servers WHERE id = $1", server_id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="MCP server not found")

    return {"status": "deleted"}


@router.post("/mcp-servers/{server_id}/test")
async def test_mcp_server(server_id: str, user: UserInfo = Depends(get_current_user)):
    """Test connectivity to an MCP server."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM mcp_servers WHERE id = $1", server_id)
        if not row:
            raise HTTPException(status_code=404, detail="MCP server not found")

    server_type = row["server_type"]

    if server_type == "http":
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
    else:
        # stdio: validate config is complete (can't test binary from admin-api container)
        command = row["command"]
        if not command:
            return {"status": "error", "message": "No command configured"}
        args = row["args"] or []
        parts = [command] + list(args)
        return {"status": "ok", "message": f"Config valid: {' '.join(parts)}"}
