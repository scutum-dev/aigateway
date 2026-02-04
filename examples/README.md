# Agent Gateway Platform Examples

This directory contains examples and guides for using the Agent Gateway platform components.

## Overview

The Agent Gateway platform provides three main gateways:

1. **LLM Gateway (Port 3000)** - Unified API for LLM providers with cost tracking
2. **MCP Gateway (Port 3001)** - Tool federation using Model Context Protocol
3. **A2A Gateway (Port 3002)** - Agent-to-agent communication and orchestration

## Quick Start

### Prerequisites

```bash
# Set environment variables
export GATEWAY_URL="http://agentgateway.agentgateway.svc.cluster.local"
export API_KEY="your-api-key"

# Verify gateway is running
kubectl get pods -n agentgateway
kubectl get pods -n mcp-servers
kubectl get pods -n a2a
```

### Test Connectivity

```bash
# Test LLM Gateway
curl -X POST "$GATEWAY_URL:9000/v1/chat/completions" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4o", "messages": [{"role": "user", "content": "Hello!"}]}'

# Test MCP Gateway
curl -X GET "$GATEWAY_URL:9001/mcp/tools" \
  -H "Authorization: Bearer $API_KEY"

# Test A2A Gateway
curl -X GET "$GATEWAY_URL:9002/a2a/agents" \
  -H "Authorization: Bearer $API_KEY"
```

## Examples

### 1. MCP Gateway Usage

**File:** [mcp-usage.md](./mcp-usage.md)

Learn how to:
- Discover available MCP tools
- Invoke filesystem operations
- Query databases via MCP
- Analyze code using MCP tools
- Integrate MCP with LLMs

**Quick Example:**

```bash
# List available tools
curl "$GATEWAY_URL:9001/mcp/tools" -H "Authorization: Bearer $API_KEY"

# Read a file
curl -X POST "$GATEWAY_URL:9001/mcp/invoke" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "filesystem.read_file",
    "params": {"path": "/data/example.txt"}
  }'
```

### 2. Agent-to-Agent Communication

**File:** [agent-communication.md](./agent-communication.md)

Learn how to:
- Discover agents dynamically
- Match capabilities to tasks
- Send messages between agents
- Implement multi-agent workflows
- Use WebSocket for streaming

**Quick Example:**

```bash
# List agents
curl "$GATEWAY_URL:9002/a2a/agents" -H "Authorization: Bearer $API_KEY"

# Send message to agent
curl -X POST "$GATEWAY_URL:9002/a2a/send" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "from": "client",
    "to": "code-assistant",
    "capability": "code-review",
    "message": {"code": "def add(a,b): return a+b", "language": "python"}
  }'
```

### 3. Multi-Agent Workflow

**File:** [a2a-workflow.yaml](./a2a-workflow.yaml)

Complete workflow example demonstrating:
- Sequential agent execution
- Parallel agent execution
- Capability-based routing
- Result aggregation

**Deploy and Run:**

```bash
# Deploy workflow
kubectl apply -f examples/a2a-workflow.yaml

# Run workflow job
kubectl create job --from=configmap/workflow-example run-workflow -n a2a

# View logs
kubectl logs -n a2a job/run-workflow -f
```

## Use Cases

### Use Case 1: Code Review Pipeline

Combine multiple agents for comprehensive code review:

```
User Code → Research Agent (find best practices)
         ↓
    Code Assistant (analyze & review)
         ↓
    Data Analysis (performance metrics)
         ↓
    Aggregated Report
```

### Use Case 2: Data Analysis Workflow

Natural language to SQL to insights:

```
User Question → Data Analysis Agent (generate SQL)
             ↓
        Database MCP (execute query)
             ↓
        Data Analysis Agent (analyze results)
             ↓
        Research Agent (summarize findings)
```

### Use Case 3: Autonomous Development

Agent collaboration for feature development:

```
Feature Request → Research Agent (find examples)
               ↓
          Code Assistant (generate code)
               ↓
          Code Analysis MCP (lint & analyze)
               ↓
          Code Assistant (refine)
               ↓
          Filesystem MCP (write files)
```

## SDK Examples

### Python

```python
from agent_gateway import AgentGatewayClient

client = AgentGatewayClient(
    base_url="http://agentgateway.agentgateway.svc.cluster.local",
    api_key="your-api-key"
)

# Use MCP tools
result = client.mcp.invoke_tool(
    tool="filesystem.read_file",
    params={"path": "/data/config.yaml"}
)

# Communicate with agents
result = client.a2a.send_message(
    to_agent="code-assistant",
    capability="code-review",
    message={"code": "...", "language": "python"}
)

# Chat with LLM
result = client.llm.chat(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### JavaScript/TypeScript

```typescript
import { AgentGatewayClient } from '@agent-gateway/client';

const client = new AgentGatewayClient({
  baseUrl: 'http://agentgateway.agentgateway.svc.cluster.local',
  apiKey: 'your-api-key'
});

// Use MCP tools
const result = await client.mcp.invokeTool({
  tool: 'filesystem.read_file',
  params: { path: '/data/config.yaml' }
});

// Communicate with agents
const review = await client.a2a.sendMessage({
  toAgent: 'code-assistant',
  capability: 'code-review',
  message: { code: '...', language: 'python' }
});
```

### Go

```go
package main

import (
    "github.com/agent-gateway/go-client"
)

func main() {
    client := agentgateway.NewClient(&agentgateway.Config{
        BaseURL: "http://agentgateway.agentgateway.svc.cluster.local",
        APIKey:  "your-api-key",
    })

    // Use MCP tools
    result, err := client.MCP.InvokeTool(ctx, &agentgateway.InvokeToolRequest{
        Tool: "filesystem.read_file",
        Params: map[string]interface{}{
            "path": "/data/config.yaml",
        },
    })

    // Communicate with agents
    result, err := client.A2A.SendMessage(ctx, &agentgateway.SendMessageRequest{
        ToAgent:    "code-assistant",
        Capability: "code-review",
        Message: map[string]interface{}{
            "code":     "...",
            "language": "python",
        },
    })
}
```

## Architecture Diagrams

### Full Platform Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Kubernetes Cluster                          │
└─────────────────────────────────────────────────────────────────┘
                              │
    ┌─────────────────────────┼─────────────────────────┐
    │                         │                         │
    ▼                         ▼                         ▼
┌──────────┐          ┌──────────────┐          ┌─────────────┐
│ External │          │    vLLM      │          │ MCP Servers │
│   LLMs   │          │  Self-hosted │          │   & Tools   │
└──────────┘          └──────────────┘          └─────────────┘
    ▲                         ▲                         ▲
    │                         │                         │
    └─────────────────────────┼─────────────────────────┘
                              │
              ┌───────────────────────────────┐
              │   Agent Gateway (Rust)        │
              │  ┌────────────────────────┐   │
              │  │ LLM Gateway :9000      │   │
              │  │ MCP Gateway :9001      │   │
              │  │ A2A Gateway :9002      │   │
              │  └────────────────────────┘   │
              └───────────────────────────────┘
                              ▲
                              │
              ┌───────────────────────────────┐
              │   LiteLLM Proxy (Python)      │
              │  • Cost tracking              │
              │  • Budget management          │
              │  • Provider routing           │
              └───────────────────────────────┘
                              ▲
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐      ┌─────────────┐      ┌─────────────┐
│   Agents     │      │ Workflows   │      │  API Clients│
│  (A2A)       │      │Orchestrators│      │             │
└──────────────┘      └─────────────┘      └─────────────┘
```

### MCP Gateway Architecture

```
┌────────────────┐
│  LLM or Agent  │
└────────┬───────┘
         │ List tools / Invoke tool
         ▼
┌────────────────────────┐
│   MCP Gateway          │
│  ┌──────────────────┐  │
│  │ Tool Aggregator  │  │  Discovers and aggregates
│  │ (Deduplication)  │  │  tools from all MCP servers
│  └──────────────────┘  │
└────────┬───────────────┘
         │
    ┌────┴────┬─────────┬────────┐
    ▼         ▼         ▼        ▼
┌────────┐ ┌───────┐ ┌──────┐ ┌─────────┐
│FileSystem│Database│ Code  │ │OpenAPI  │
│  MCP   │ │  MCP  │ │Analysis│Bridge   │
└────────┘ └───────┘ └──────┘ └─────────┘
```

### A2A Gateway Architecture

```
┌──────────────┐
│ Orchestrator │
└──────┬───────┘
       │ Discover / Send message
       ▼
┌──────────────────────┐
│   A2A Gateway        │
│ ┌─────────────────┐  │
│ │ Capability      │  │  Matches capabilities
│ │ Matcher         │  │  to find best agent
│ └─────────────────┘  │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│  Agent Registry      │
│  (Service Discovery) │
└──────┬───────────────┘
       │
  ┌────┴────┬──────────┬────────┐
  ▼         ▼          ▼        ▼
┌────┐   ┌────┐    ┌────┐   ┌────┐
│Code│   │Data│    │Research│ │...│
│Asst│   │Anal│    │ Agent │ │   │
└────┘   └────┘    └────┘   └────┘
```

## Monitoring

### View Metrics

```bash
# Forward Prometheus
kubectl port-forward -n observability svc/prometheus 9090:9090

# Open in browser
open http://localhost:9090

# Query MCP metrics
agentgateway_mcp_requests_total
agentgateway_mcp_duration_seconds

# Query A2A metrics
agentgateway_a2a_messages_total
agentgateway_a2a_agent_up
```

### View Traces

```bash
# Forward Jaeger
kubectl port-forward -n observability svc/jaeger 16686:16686

# Open in browser
open http://localhost:16686

# Search for traces:
# - Service: mcp-gateway, a2a-gateway
# - Operation: mcp.invoke_tool, a2a.send_message
```

### View Dashboards

```bash
# Forward Grafana
kubectl port-forward -n observability svc/grafana 3000:9000

# Open in browser
open http://localhost:9000

# Dashboards:
# - Agent Gateway Overview
# - MCP Gateway Metrics
# - A2A Agent Communication
# - LiteLLM Cost Tracking
```

## Troubleshooting

### Common Issues

1. **Agent not found**
   ```bash
   kubectl get pods -n a2a
   kubectl logs -n a2a -l app.kubernetes.io/type=agent
   ```

2. **MCP server unavailable**
   ```bash
   kubectl get pods -n mcp-servers
   kubectl logs -n mcp-servers -l app.kubernetes.io/type=mcp-server
   ```

3. **Authentication failed**
   ```bash
   # Verify API key
   echo $API_KEY

   # Check gateway logs
   kubectl logs -n agentgateway -l app.kubernetes.io/name=agentgateway
   ```

4. **Rate limit exceeded**
   ```bash
   # Check rate limit config
   kubectl get configmap -n agentgateway agentgateway-config -o yaml
   ```

## Best Practices

1. **Use capability-based routing** - Let the gateway find the best agent
2. **Cache tool lists** - Tools don't change frequently
3. **Implement retries** - Agents may be temporarily unavailable
4. **Monitor metrics** - Track usage and errors
5. **Set timeouts** - Don't wait indefinitely
6. **Use read-only tools** - Prefer read operations for safety
7. **Validate inputs** - Check parameters before invoking tools

## Next Steps

- [Platform Documentation](../README.md)
- [Configuration Guide](../config/README.md)
- [Deployment Guide](../kubernetes/README.md)
- [Security Guide](../docs/security/threat-model.md)
- [FinOps Guide](../docs/finops/cost-tracking.md)

## Contributing

See examples you'd like to add? Submit a PR!

1. Fork the repository
2. Create your example file
3. Add it to this README
4. Submit a pull request

## License

MIT License - see [LICENSE](../LICENSE) for details
