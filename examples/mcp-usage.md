# MCP Gateway Usage Guide

This guide demonstrates how to use the MCP (Model Context Protocol) Gateway to access federated tools from multiple MCP servers.

## Overview

The MCP Gateway aggregates tools from multiple MCP servers and exposes them through a unified API. This allows LLMs and agents to discover and use tools without knowing which server provides them.

## Architecture

```
┌─────────────┐
│ LLM / Agent │
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│   Agent Gateway     │
│  (Port 9000/3000)   │
│  /mcp/* routes      │
└──────┬──────────────┘
       │ stdio
       ├──────────────────┐──────────────────┐
       │                  │                  │
       ▼                  ▼                  ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ Filesystem   │   │  Database    │   │ Brave Search │
│ MCP Server   │   │  MCP Server  │   │ MCP Server   │
└──────────────┘   └──────────────┘   └──────────────┘
```

## Authentication

MCP Gateway requires authentication via JWT or API key:

```bash
# For local development (docker-compose)
export MCP_API_KEY="$LITELLM_KEY"
export MCP_GATEWAY_URL="http://localhost:9000"

# For Kubernetes deployment
export MCP_API_KEY="your-api-key"
export MCP_GATEWAY_URL="http://agentgateway.agentgateway.svc.cluster.local:9000"
```

## Discovering Available Tools

List all available tools from federated MCP servers:

```bash
curl -X GET "$MCP_GATEWAY_URL/mcp/tools" \
  -H "Authorization: Bearer $MCP_API_KEY" \
  | jq
```

**Response:**
```json
{
  "tools": [
    {
      "name": "filesystem.read_file",
      "description": "Read contents of a file",
      "server": "filesystem",
      "inputSchema": {
        "type": "object",
        "properties": {
          "path": {
            "type": "string",
            "description": "Path to the file to read"
          }
        },
        "required": ["path"]
      }
    },
    {
      "name": "database.query",
      "description": "Execute a SELECT query on the database",
      "server": "database",
      "inputSchema": {
        "type": "object",
        "properties": {
          "sql": {
            "type": "string",
            "description": "SQL SELECT query to execute"
          }
        },
        "required": ["sql"]
      }
    },
    {
      "name": "code-analysis.analyze_code",
      "description": "Analyze code structure and complexity",
      "server": "code-analysis",
      "inputSchema": {
        "type": "object",
        "properties": {
          "code": {"type": "string"},
          "language": {"type": "string"}
        },
        "required": ["code", "language"]
      }
    }
  ]
}
```

## Using Filesystem Tools

### Read a File

```bash
curl -X POST "$MCP_GATEWAY_URL/mcp/invoke" \
  -H "Authorization: Bearer $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "filesystem.read_file",
    "params": {
      "path": "/data/example.txt"
    }
  }' | jq
```

**Response:**
```json
{
  "result": {
    "content": "Hello, world!\nThis is an example file.",
    "size": 42,
    "mime_type": "text/plain"
  },
  "metadata": {
    "execution_time_ms": 15,
    "server": "filesystem",
    "tool": "read_file"
  }
}
```

### List Directory

```bash
curl -X POST "$MCP_GATEWAY_URL/mcp/invoke" \
  -H "Authorization: Bearer $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "filesystem.list_directory",
    "params": {
      "path": "/data",
      "recursive": false
    }
  }' | jq
```

### Search Files

```bash
curl -X POST "$MCP_GATEWAY_URL/mcp/invoke" \
  -H "Authorization: Bearer $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "filesystem.search_files",
    "params": {
      "path": "/data",
      "pattern": "*.txt"
    }
  }' | jq
```

## Using Database Tools

### Query Database

```bash
curl -X POST "$MCP_GATEWAY_URL/mcp/invoke" \
  -H "Authorization: Bearer $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "database.query",
    "params": {
      "sql": "SELECT COUNT(*) as total FROM users WHERE active = true"
    }
  }' | jq
```

**Response:**
```json
{
  "result": {
    "rows": [
      {"total": 1234}
    ],
    "columns": ["total"],
    "row_count": 1
  },
  "metadata": {
    "execution_time_ms": 42,
    "server": "database",
    "tool": "query"
  }
}
```

### List Tables

```bash
curl -X POST "$MCP_GATEWAY_URL/mcp/invoke" \
  -H "Authorization: Bearer $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "database.list_tables"
  }' | jq
```

### Get Schema Info

```bash
curl -X POST "$MCP_GATEWAY_URL/mcp/invoke" \
  -H "Authorization: Bearer $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "database.schema_info",
    "params": {
      "table": "users"
    }
  }' | jq
```

## Using Code Analysis Tools

### Analyze Code

```bash
curl -X POST "$MCP_GATEWAY_URL/mcp/invoke" \
  -H "Authorization: Bearer $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "code-analysis.analyze_code",
    "params": {
      "code": "def calculate_fibonacci(n):\n    if n <= 1:\n        return n\n    return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)",
      "language": "python",
      "metrics": ["complexity", "loc", "functions"]
    }
  }' | jq
```

**Response:**
```json
{
  "result": {
    "metrics": {
      "complexity": {
        "cyclomatic": 3,
        "cognitive": 4
      },
      "loc": {
        "total": 4,
        "code": 4,
        "comments": 0
      },
      "functions": {
        "count": 1,
        "names": ["calculate_fibonacci"]
      }
    },
    "issues": [
      {
        "severity": "warning",
        "message": "Recursive function without memoization may be inefficient",
        "line": 1
      }
    ]
  }
}
```

### Lint Code

```bash
curl -X POST "$MCP_GATEWAY_URL/mcp/invoke" \
  -H "Authorization: Bearer $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "code-analysis.lint_code",
    "params": {
      "code": "const x = 5;\nif (x = 10) { console.log(x); }",
      "language": "javascript"
    }
  }' | jq
```

### Suggest Improvements

```bash
curl -X POST "$MCP_GATEWAY_URL/mcp/invoke" \
  -H "Authorization: Bearer $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "code-analysis.suggest_improvements",
    "params": {
      "code": "for i in range(len(items)):\n    print(items[i])",
      "language": "python",
      "focus": "readability"
    }
  }' | jq
```

## Using MCP with LLMs

### OpenAI SDK

```python
import openai
import requests

# Configure OpenAI to use Agent Gateway
openai.api_base = "http://agentgateway.agentgateway.svc.cluster.local:9000/v1"
openai.api_key = "your-api-key"

# Get available MCP tools
mcp_tools = requests.get(
    "http://agentgateway.agentgateway.svc.cluster.local:9001/mcp/tools",
    headers={"Authorization": f"Bearer {openai.api_key}"}
).json()

# Convert MCP tools to OpenAI function format
tools = [
    {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["inputSchema"]
        }
    }
    for tool in mcp_tools["tools"]
]

# Create chat completion with tools
response = openai.ChatCompletion.create(
    model="gpt-4o",
    messages=[
        {"role": "user", "content": "Read the file /data/config.yaml and summarize it"}
    ],
    tools=tools,
    tool_choice="auto"
)

# If model calls a tool, invoke it via MCP Gateway
if response.choices[0].message.tool_calls:
    for tool_call in response.choices[0].message.tool_calls:
        tool_result = requests.post(
            "http://agentgateway.agentgateway.svc.cluster.local:9001/mcp/invoke",
            headers={"Authorization": f"Bearer {openai.api_key}"},
            json={
                "tool": tool_call.function.name,
                "params": json.loads(tool_call.function.arguments)
            }
        ).json()

        print(f"Tool: {tool_call.function.name}")
        print(f"Result: {tool_result['result']}")
```

## Error Handling

MCP Gateway returns standard error responses:

```json
{
  "error": {
    "code": "tool_not_found",
    "message": "Tool 'invalid.tool' not found",
    "details": {
      "available_servers": ["filesystem", "database", "code-analysis"]
    }
  }
}
```

### Common Error Codes

- `authentication_failed` - Invalid or missing API key/JWT
- `tool_not_found` - Requested tool doesn't exist
- `invalid_parameters` - Tool parameters don't match schema
- `server_unavailable` - MCP server is down or unreachable
- `execution_timeout` - Tool execution exceeded timeout
- `rate_limit_exceeded` - Too many requests

## Observability

### Metrics

MCP Gateway exposes Prometheus metrics at `:9090/metrics`:

```bash
# Tool invocation count
agentgateway_mcp_requests_total{server="filesystem",tool="read_file",status="success"} 1234

# Tool execution duration
agentgateway_mcp_duration_seconds{server="database",tool="query",quantile="0.99"} 0.042

# Server health
agentgateway_mcp_server_up{server="filesystem"} 1
```

### Tracing

View distributed traces in Jaeger:

```bash
# Forward Jaeger UI
kubectl port-forward -n observability svc/jaeger 16686:16686

# Open in browser
open http://localhost:16686
```

Look for traces with service name `mcp-gateway` and spans like:
- `mcp.list_tools`
- `mcp.invoke_tool`
- `mcp.server.filesystem.read_file`

## Security

### Cedar Policies

MCP tool access is controlled by Cedar policies. Example policy:

```cedar
// Allow developers to use read-only filesystem tools
permit(
    principal in Group::"developers",
    action in [
        Action::"mcp.list_tools",
        Action::"mcp.invoke_tool"
    ],
    resource in [
        Tool::"filesystem.read_file",
        Tool::"filesystem.list_directory",
        Tool::"filesystem.search_files"
    ]
);

// Forbid write operations unless explicitly allowed
forbid(
    principal,
    action == Action::"mcp.invoke_tool",
    resource in [
        Tool::"filesystem.write_file",
        Tool::"database.execute_sql"
    ]
) unless {
    principal in Group::"admins"
};
```

## Rate Limiting

Rate limits are enforced per tool:

- `filesystem.read_file`: 100/min
- `filesystem.write_file`: 10/min
- `database.query`: 50/min
- `code-analysis.analyze_code`: 50/min

Exceeding limits returns HTTP 429:

```json
{
  "error": {
    "code": "rate_limit_exceeded",
    "message": "Rate limit exceeded for filesystem.read_file",
    "retry_after": 42
  }
}
```

## Best Practices

1. **Cache tool lists** - Tools don't change frequently, cache for 5+ minutes
2. **Use specific tools** - Prefer `filesystem.read_file` over discovering all tools
3. **Handle errors gracefully** - Servers may be temporarily unavailable
4. **Set timeouts** - Don't wait indefinitely for tool results
5. **Monitor metrics** - Track tool usage and error rates
6. **Validate inputs** - Check parameters before invoking tools
7. **Use read-only tools** - Prefer read operations for safety

## Troubleshooting

### Tool Not Found

```bash
# Check available tools
curl -X GET "$MCP_GATEWAY_URL/mcp/tools" \
  -H "Authorization: Bearer $MCP_API_KEY" | jq '.tools[].name'
```

### Server Unavailable

```bash
# Check MCP server health
kubectl get pods -n mcp-servers
kubectl logs -n mcp-servers -l app.kubernetes.io/name=filesystem-mcp
```

### Authentication Failed

```bash
# Verify API key
echo $MCP_API_KEY

# Test authentication
curl -X GET "$MCP_GATEWAY_URL/mcp/tools" \
  -H "Authorization: Bearer $MCP_API_KEY" -v
```

## Next Steps

- [A2A Gateway Usage](./a2a-workflow.yaml) - Agent-to-agent communication
- [Multi-Agent Workflow](./multi-agent-workflow.yaml) - Orchestrating multiple agents
- [Cedar Policies](../config/agentgateway/policies/rbac.cedar) - Access control
