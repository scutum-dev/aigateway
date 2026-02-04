# Agent-to-Agent Communication Guide

This guide demonstrates how to use the A2A (Agent-to-Agent) Gateway for agent discovery, capability matching, and inter-agent communication.

## Overview

The A2A Gateway enables agents to:
- **Discover** other agents dynamically
- **Match** capabilities to find the right agent for a task
- **Communicate** using standard protocols (HTTP, gRPC, WebSocket)
- **Orchestrate** multi-agent workflows

## Architecture

```
┌──────────────┐
│ Orchestrator │
└──────┬───────┘
       │
       ▼
┌─────────────────────┐
│   Agent Gateway     │
│   (Port 9000/3000)  │
│   /a2a/* routes     │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  Agent Registry     │
│  (Service Discovery)│
└──────┬──────────────┘
       │
       ├───────────────┬──────────────┐
       │               │              │
       ▼               ▼              ▼
┌─────────────┐ ┌────────────┐ ┌─────────────┐
│Code         │ │Data        │ │Research     │
│Assistant    │ │Analysis    │ │Agent        │
└─────────────┘ └────────────┘ └─────────────┘
```

## Setup

```bash
# For local development (docker-compose)
export A2A_API_KEY="$LITELLM_KEY"
export A2A_GATEWAY_URL="http://localhost:9000"

# For Kubernetes deployment
export A2A_API_KEY="your-api-key"
export A2A_GATEWAY_URL="http://agentgateway.agentgateway.svc.cluster.local:9000"
```

## Agent Discovery

### List All Agents

```bash
curl -X GET "$A2A_GATEWAY_URL/a2a/agents" \
  -H "Authorization: Bearer $A2A_API_KEY" \
  | jq
```

**Response:**
```json
{
  "agents": [
    {
      "name": "code-assistant",
      "description": "Code analysis and review agent",
      "status": "healthy",
      "endpoint": "http://code-assistant.a2a.svc.cluster.local:8080",
      "version": "1.0.0",
      "metadata": {
        "author": "Platform Team",
        "tags": ["code", "development", "analysis"]
      }
    },
    {
      "name": "data-analysis",
      "description": "Data analysis and SQL agent",
      "status": "healthy",
      "endpoint": "http://data-analysis.a2a.svc.cluster.local:8080",
      "version": "1.0.0"
    },
    {
      "name": "research-agent",
      "description": "Research and information gathering",
      "status": "healthy",
      "endpoint": "http://research-agent.a2a.svc.cluster.local:8080",
      "version": "1.0.0"
    }
  ],
  "total": 3
}
```

### Get Agent Details

```bash
curl -X GET "$A2A_GATEWAY_URL/a2a/agents/code-assistant" \
  -H "Authorization: Bearer $A2A_API_KEY" \
  | jq
```

**Response:**
```json
{
  "name": "code-assistant",
  "description": "Agent specialized in code analysis, review, and refactoring",
  "version": "1.0.0",
  "status": "healthy",
  "endpoint": "http://code-assistant.a2a.svc.cluster.local:8080",
  "capabilities": [
    {
      "name": "code-review",
      "description": "Review code for quality, bugs, and improvements"
    },
    {
      "name": "refactor-code",
      "description": "Suggest refactoring improvements"
    },
    {
      "name": "explain-code",
      "description": "Explain what code does"
    }
  ],
  "requirements": {
    "mcp_servers": ["code-analysis"],
    "models": ["gpt-4o", "claude-3-5-sonnet"]
  },
  "health": {
    "status": "healthy",
    "uptime": "2h15m",
    "requests_handled": 1234,
    "success_rate": 0.995
  }
}
```

## Capability Discovery

### List Agent Capabilities

```bash
curl -X GET "$A2A_GATEWAY_URL/a2a/agents/code-assistant/capabilities" \
  -H "Authorization: Bearer $A2A_API_KEY" \
  | jq
```

**Response:**
```json
{
  "agent": "code-assistant",
  "capabilities": [
    {
      "name": "code-review",
      "description": "Review code for quality, bugs, and improvements",
      "parameters": {
        "type": "object",
        "properties": {
          "code": {"type": "string", "description": "Source code to review"},
          "language": {"type": "string", "description": "Programming language"}
        },
        "required": ["code", "language"]
      },
      "returns": {
        "type": "object",
        "properties": {
          "issues": {"type": "array"},
          "suggestions": {"type": "array"},
          "rating": {"type": "number"}
        }
      }
    }
  ]
}
```

### Find Agent by Capability

```bash
curl -X POST "$A2A_GATEWAY_URL/a2a/find" \
  -H "Authorization: Bearer $A2A_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "capability": "code-review",
    "requirements": {
      "language": "python"
    }
  }' | jq
```

**Response:**
```json
{
  "matches": [
    {
      "agent": "code-assistant",
      "score": 0.95,
      "capability": "code-review",
      "reason": "Exact capability match with language support"
    }
  ]
}
```

## Agent Communication

### Direct Message to Agent

```bash
curl -X POST "$A2A_GATEWAY_URL/a2a/send" \
  -H "Authorization: Bearer $A2A_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "from": "orchestrator",
    "to": "code-assistant",
    "capability": "code-review",
    "message": {
      "code": "def hello():\n    print(\"Hello, world!\")",
      "language": "python"
    }
  }' | jq
```

**Response:**
```json
{
  "message_id": "msg_abc123",
  "from": "code-assistant",
  "to": "orchestrator",
  "timestamp": "2025-02-04T10:30:00Z",
  "result": {
    "issues": [],
    "suggestions": [
      {
        "type": "docstring",
        "message": "Add docstring to function",
        "line": 1
      }
    ],
    "rating": 8.5
  },
  "metadata": {
    "execution_time_ms": 1200,
    "model_used": "gpt-4o"
  }
}
```

### Capability-Based Routing

Let the gateway find the best agent:

```bash
curl -X POST "$A2A_GATEWAY_URL/a2a/invoke" \
  -H "Authorization: Bearer $A2A_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "capability": "analyze-data",
    "message": {
      "query": "Find users who signed up in the last 30 days",
      "dataset": "users"
    }
  }' | jq
```

The gateway will:
1. Find agents with `analyze-data` capability (data-analysis)
2. Route the message to the best match
3. Return the response

### Broadcast to Multiple Agents

Send a message to multiple agents:

```bash
curl -X POST "$A2A_GATEWAY_URL/a2a/broadcast" \
  -H "Authorization: Bearer $A2A_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "from": "orchestrator",
    "to": ["code-assistant", "research-agent"],
    "message": {
      "task": "Find information about Python async/await best practices"
    }
  }' | jq
```

## Multi-Agent Workflows

### Sequential Workflow

Chain multiple agents together:

```bash
#!/bin/bash

# Step 1: Research agent finds papers
RESEARCH_RESULT=$(curl -s -X POST "$A2A_GATEWAY_URL/a2a/send" \
  -H "Authorization: Bearer $A2A_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "from": "workflow",
    "to": "research-agent",
    "capability": "find-papers",
    "message": {
      "query": "transformer architecture improvements",
      "field": "computer-science"
    }
  }')

echo "Research completed: $RESEARCH_RESULT"

# Step 2: Research agent summarizes findings
SUMMARY=$(curl -s -X POST "$A2A_GATEWAY_URL/a2a/send" \
  -H "Authorization: Bearer $A2A_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"from\": \"workflow\",
    \"to\": \"research-agent\",
    \"capability\": \"summarize-content\",
    \"message\": {
      \"content\": \"$RESEARCH_RESULT\",
      \"style\": \"technical\"
    }
  }")

echo "Summary: $SUMMARY"
```

### Parallel Workflow

Execute multiple agents in parallel:

```bash
#!/bin/bash

# Start both agents in parallel
CODE_REVIEW=$(curl -s -X POST "$A2A_GATEWAY_URL/a2a/send" \
  -H "Authorization: Bearer $A2A_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "from": "workflow",
    "to": "code-assistant",
    "capability": "code-review",
    "message": {"code": "..."}
  }' &)

DATA_ANALYSIS=$(curl -s -X POST "$A2A_GATEWAY_URL/a2a/send" \
  -H "Authorization: Bearer $A2A_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "from": "workflow",
    "to": "data-analysis",
    "capability": "analyze-data",
    "message": {"query": "..."}
  }' &)

# Wait for both to complete
wait

echo "Code Review: $CODE_REVIEW"
echo "Data Analysis: $DATA_ANALYSIS"
```

## Python SDK Example

```python
import requests
from typing import Dict, Any, List

class A2AClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def list_agents(self) -> List[Dict[str, Any]]:
        """List all available agents."""
        response = requests.get(
            f"{self.base_url}/a2a/agents",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()["agents"]

    def get_agent_capabilities(self, agent_name: str) -> List[Dict[str, Any]]:
        """Get capabilities of a specific agent."""
        response = requests.get(
            f"{self.base_url}/a2a/agents/{agent_name}/capabilities",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()["capabilities"]

    def send_message(
        self,
        to_agent: str,
        capability: str,
        message: Dict[str, Any],
        from_agent: str = "client"
    ) -> Dict[str, Any]:
        """Send a message to an agent."""
        response = requests.post(
            f"{self.base_url}/a2a/send",
            headers=self.headers,
            json={
                "from": from_agent,
                "to": to_agent,
                "capability": capability,
                "message": message
            }
        )
        response.raise_for_status()
        return response.json()

    def invoke_capability(
        self,
        capability: str,
        message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Invoke a capability (gateway finds best agent)."""
        response = requests.post(
            f"{self.base_url}/a2a/invoke",
            headers=self.headers,
            json={
                "capability": capability,
                "message": message
            }
        )
        response.raise_for_status()
        return response.json()


# Usage
client = A2AClient(
    base_url="http://agentgateway.agentgateway.svc.cluster.local:9002",
    api_key="your-api-key"
)

# List agents
agents = client.list_agents()
print(f"Found {len(agents)} agents")

# Review code
result = client.send_message(
    to_agent="code-assistant",
    capability="code-review",
    message={
        "code": "def add(a, b): return a + b",
        "language": "python"
    }
)
print(f"Code review: {result['result']}")

# Invoke capability (auto-routing)
result = client.invoke_capability(
    capability="research-topic",
    message={
        "topic": "Kubernetes best practices",
        "depth": "detailed"
    }
)
print(f"Research: {result['result']}")
```

## WebSocket Streaming

For real-time communication:

```javascript
const WebSocket = require('ws');

const ws = new WebSocket('ws://agentgateway.agentgateway.svc.cluster.local:8081');

ws.on('open', () => {
  // Authenticate
  ws.send(JSON.stringify({
    type: 'auth',
    token: 'your-api-key'
  }));

  // Subscribe to agent messages
  ws.send(JSON.stringify({
    type: 'subscribe',
    agent: 'code-assistant'
  }));

  // Send message
  ws.send(JSON.stringify({
    type: 'message',
    to: 'code-assistant',
    capability: 'code-review',
    message: {
      code: 'def hello(): print("hi")',
      language: 'python'
    }
  }));
});

ws.on('message', (data) => {
  const msg = JSON.parse(data);
  console.log('Received:', msg);
});
```

## Error Handling

```python
try:
    result = client.send_message(
        to_agent="code-assistant",
        capability="code-review",
        message={"code": "..."}
    )
except requests.HTTPError as e:
    if e.response.status_code == 404:
        print("Agent not found")
    elif e.response.status_code == 429:
        print("Rate limit exceeded")
    elif e.response.status_code == 503:
        print("Agent unavailable")
    else:
        print(f"Error: {e.response.json()}")
```

## Observability

### Metrics

```bash
# Message count
agentgateway_a2a_messages_total{from="orchestrator",to="code-assistant",status="success"} 456

# Message duration
agentgateway_a2a_duration_seconds{from="orchestrator",to="code-assistant",quantile="0.99"} 1.2

# Agent health
agentgateway_a2a_agent_up{agent="code-assistant"} 1
```

### Tracing

View A2A message traces in Jaeger:

```bash
kubectl port-forward -n observability svc/jaeger 16686:16686
open http://localhost:16686
```

Look for spans:
- `a2a.discover_agents`
- `a2a.send_message`
- `a2a.agent.code-assistant.code-review`

## Security

### Authentication

All A2A requests require authentication:
- **JWT tokens** - For agent-to-agent communication
- **API keys** - For external clients

### Authorization

Cedar policies control what agents can do:

```cedar
// Allow code-assistant to communicate with research-agent
permit(
    principal == Agent::"code-assistant",
    action == Action::"a2a.send_message",
    resource == Agent::"research-agent"
);

// Allow orchestrator to broadcast
permit(
    principal == Agent::"orchestrator",
    action == Action::"a2a.broadcast",
    resource
);
```

## Best Practices

1. **Use capability-based routing** - Let the gateway find the best agent
2. **Handle agent unavailability** - Agents may be down or scaling
3. **Implement timeouts** - Don't wait forever for responses
4. **Monitor metrics** - Track message flow and errors
5. **Version agents** - Use semantic versioning for compatibility
6. **Cache capabilities** - Capabilities don't change frequently
7. **Use message queues** - For async, fire-and-forget communication

## Troubleshooting

### Agent Not Found

```bash
# List all agents
kubectl get pods -n a2a -l app.kubernetes.io/type=agent

# Check agent logs
kubectl logs -n a2a -l app.kubernetes.io/name=code-assistant
```

### Agent Unhealthy

```bash
# Check agent health
curl "$A2A_GATEWAY_URL/a2a/agents/code-assistant" | jq '.health'

# Check agent registry
kubectl logs -n a2a -l app.kubernetes.io/name=agent-registry
```

### Message Timeout

Increase timeout or check agent performance:

```bash
# Check message metrics
curl http://agentgateway:9090/metrics | grep a2a_duration
```

## Next Steps

- [MCP Gateway Usage](./mcp-usage.md) - Tool federation
- [Multi-Agent Workflow](./a2a-workflow.yaml) - Complete workflow example
- [Cedar Policies](../config/agentgateway/policies/rbac.cedar) - Access control
