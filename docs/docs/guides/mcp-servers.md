# MCP Servers Guide

Extend the AI Control Plane with external tools using the Model Context Protocol (MCP).

## Overview

MCP (Model Context Protocol) is a standard for connecting AI models to external tools and data sources. The AI Control Plane supports MCP through two components:

1. **Admin API + UI** -- configure and manage MCP server definitions in PostgreSQL
2. **Agent Gateway** -- a Rust-based runtime that connects to MCP servers and exposes tools to AI agents

```
AI Agent ──▶ Agent Gateway (:9000) ──▶ MCP Server (stdio/http)
                                              │
                                    ┌─────────┴─────────┐
                                    │                    │
                              stdio servers        http servers
                              (local process)      (remote endpoint)
                                    │                    │
                                    ▼                    ▼
                              Brave Search         Cloud Tool APIs
                              GitHub CLI           Custom Services
                              File System          Database Queries
```

## Server Types

### stdio Servers

stdio servers run as local child processes. The Agent Gateway spawns the process, communicates via stdin/stdout, and manages the lifecycle.

**Best for:** Local tools, CLI wrappers, file system access.

**Examples:**
- `npx -y @anthropic/mcp-server-brave-search` -- web search
- `npx -y @anthropic/mcp-server-github` -- GitHub operations
- `npx -y @anthropic/mcp-server-filesystem` -- file operations

### http (SSE) Servers

http servers are remote services that expose an HTTP endpoint using Server-Sent Events. The Agent Gateway connects over the network.

**Best for:** Cloud-hosted tools, shared services, custom APIs.

## Configuring MCP Servers

### From the Admin UI

1. Navigate to **MCP Servers** in the sidebar.
2. Click **Add Server**.
3. Fill in the form:
   - **Name:** Descriptive identifier (e.g., "brave-search")
   - **Type:** `stdio` or `http`
   - **Command** (stdio only): The executable (e.g., `npx -y @anthropic/mcp-server-brave-search`)
   - **URL** (http only): The remote endpoint
   - **Args:** Command-line arguments (space-separated)
   - **Env:** Environment variables as JSON (e.g., `{"BRAVE_API_KEY": "your-key"}`)
4. Click **Create**.

### From the API

```bash
# Get a JWT token
TOKEN=$(curl -s http://localhost:8086/auth/login \
  -H "Content-Type: application/json" \
  -d '{"api_key": "$LITELLM_KEY"}' | jq -r '.access_token')

# Create a stdio MCP server
curl -X POST http://localhost:8086/api/v1/mcp-servers \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "brave-search",
    "server_type": "stdio",
    "command": "npx",
    "args": ["-y", "@anthropic/mcp-server-brave-search"],
    "env": {"BRAVE_API_KEY": "your-key"},
    "is_active": true
  }'

# Create an http MCP server
curl -X POST http://localhost:8086/api/v1/mcp-servers \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "custom-tools",
    "server_type": "http",
    "url": "https://tools.example.com/mcp",
    "is_active": true
  }'
```

## Testing Servers

Verify a server is configured correctly before deploying:

```bash
# Test a specific server
curl -X POST http://localhost:8086/api/v1/mcp-servers/{server_id}/test \
  -H "Authorization: Bearer $TOKEN"
```

- **http servers:** The gateway makes an HTTP request to the configured URL and reports the status code.
- **stdio servers:** The gateway validates the command and arguments are configured correctly.

In the Admin UI, click the **Test** button on any server card.

## Deploying to the Agent Gateway

MCP server configurations in the database are **not automatically synced** to the running Agent Gateway. This is by design -- it lets you batch changes and deploy when ready.

### Preview the Config

Before deploying, preview the YAML that will be generated:

```bash
curl http://localhost:8086/api/v1/mcp-servers/sync/preview \
  -H "Authorization: Bearer $TOKEN"
```

This returns:
```json
{
  "active_servers": 3,
  "config_yaml": "version: 2\nbinds:\n  ..."
}
```

### Deploy

Push the configuration to the live Agent Gateway:

```bash
curl -X POST http://localhost:8086/api/v1/mcp-servers/sync \
  -H "Authorization: Bearer $TOKEN"
```

This performs three steps:
1. Generates the Agent Gateway `config.yaml` from all active MCP servers
2. Patches the `agentgateway-config` Kubernetes ConfigMap
3. Triggers a rolling restart of the Agent Gateway deployment

```json
{
  "status": "synced",
  "servers_synced": 3,
  "configmap": {"status": "updated"},
  "restart": {"status": "triggered"}
}
```

### In the Admin UI

1. Click **"Preview Config"** in the MCP Servers page header to see the YAML.
2. Click **"Deploy to Gateway"** to push.
3. Confirm in the dialog.
4. A success toast confirms the deploy.

> **Note:** Deploy to Gateway requires Kubernetes. In local Docker Compose development, the Agent Gateway reads its config file directly.

## Agent Gateway Config Format

The deploy process generates a config in this format:

```yaml
version: 2
binds:
  - address: 0.0.0.0:9000
    protocol: A2A
listeners:
  - id: default
    bind: 0.0.0.0:9000
    routes:
      - id: mcp-route
        path: /mcp
        backends: [mcp-backend]
backends:
  - id: mcp-backend
    mcp:
      targets:
        - name: brave-search
          stdio:
            cmd: npx
            args: ["-y", "@anthropic/mcp-server-brave-search"]
            env:
              BRAVE_API_KEY: "your-key"
        - name: custom-tools
          sse:
            url: "https://tools.example.com/mcp"
```

stdio servers map to `stdio: {cmd, args, env}` targets. http servers map to `sse: {url}` targets.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/mcp-servers` | List all MCP server configs |
| POST | `/api/v1/mcp-servers` | Create a server config |
| GET | `/api/v1/mcp-servers/{id}` | Get a specific server |
| PUT | `/api/v1/mcp-servers/{id}` | Update a server config |
| DELETE | `/api/v1/mcp-servers/{id}` | Delete a server config |
| POST | `/api/v1/mcp-servers/{id}/test` | Test server connectivity |
| GET | `/api/v1/mcp-servers/sync/preview` | Preview Agent Gateway config |
| POST | `/api/v1/mcp-servers/sync` | Deploy to Agent Gateway |

## Common MCP Servers

| Server | Install Command | Purpose |
|--------|----------------|---------|
| Brave Search | `npx -y @anthropic/mcp-server-brave-search` | Web search via Brave |
| GitHub | `npx -y @anthropic/mcp-server-github` | GitHub repo operations |
| Filesystem | `npx -y @anthropic/mcp-server-filesystem` | Local file operations |
| PostgreSQL | `npx -y @anthropic/mcp-server-postgres` | Database queries |
| Slack | `npx -y @anthropic/mcp-server-slack` | Slack messaging |

Each requires the appropriate API keys set in the server's `env` configuration.

## Production Considerations

- **Security:** MCP server environment variables (API keys) are stored in PostgreSQL. Ensure the database is encrypted at rest and access is restricted.
- **Network:** stdio servers run inside the Agent Gateway container. http servers require network connectivity from the gateway pod.
- **Rate limits:** The Agent Gateway enforces per-tool rate limits (configurable in `config/agentgateway/mcp-config.yaml`).
- **Zero-downtime deploys:** The deploy operation uses annotation-based rolling restart. With a PodDisruptionBudget, existing connections drain gracefully.

## Related Guides

- [Admin Guide](./admin-guide.md) -- MCP Servers page walkthrough
- [API Integration Guide](./api-integration.md) -- full API endpoint reference
- [Workflows Guide](./workflows.md) -- workflows that can use MCP tools
