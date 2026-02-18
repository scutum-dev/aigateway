# AI Control Plane Examples

This directory contains examples and guides for using the AI Control Plane platform.

## Overview

The AI Control Plane platform provides:

1. **LiteLLM Proxy (Port 4000)** - Unified OpenAI-compatible API for 100+ models with cost tracking
2. **Agent Gateway (Port 9000)** - MCP tool federation + A2A agent routing (single service)
3. **Admin API (Port 8086)** - REST API for all platform configuration

## Hello World: How Organizations Use the Platform

New to the AI Control Plane? Start here:

**[Hello World Examples](./hello-world/README.md)** — Step-by-step guide showing how organizations adopt the platform:

| Example | Language | What it shows |
|---------|----------|---------------|
| `01_basic_chat.py` | Python | Simplest LLM call through the control plane |
| `02_multi_model.py` | Python | Same prompt to 3 providers, compare cost/speed |
| `03_streaming.py` | Python | Streaming responses with cost tracking |
| `04_enterprise_setup.py` | Python | Admin provisions org → teams → keys → guardrails |
| `05_cost_tracking.py` | Python | Query spend by model, team, daily trends |
| `06_guardrails_and_cache.py` | Python | DLP detectors, semantic cache, audit trail |
| `basic_chat.ts` | TypeScript | Chat + streaming + multi-model comparison |
| `admin_setup.ts` | TypeScript | Org provisioning via Admin API |

## Quick Start

### Prerequisites

```bash
# Local development (Docker Compose)
export LITELLM_URL="http://localhost:4000"
export ADMIN_API_URL="http://localhost:8086"
export API_KEY="$LITELLM_KEY"

# Verify services are running
docker compose ps
```

### Test Connectivity

```bash
# Test LiteLLM proxy
curl -X POST "$LITELLM_URL/v1/chat/completions" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4o", "messages": [{"role": "user", "content": "Hello!"}]}'

# Test Admin API
curl "$ADMIN_API_URL/health"

# Test Agent Gateway (requires --profile full)
curl http://localhost:9000/health
```

## Examples

### 1. MCP Servers (via Admin API)

MCP servers are configured through the Admin API and deployed to Agent Gateway:

```bash
# List configured MCP servers
curl "$ADMIN_API_URL/api/v1/mcp-servers" \
  -H "Authorization: Bearer $(curl -s $ADMIN_API_URL/auth/login -d '{"api_key":"'$API_KEY'"}' -H 'Content-Type: application/json' | jq -r .access_token)"

# Preview gateway config
curl "$ADMIN_API_URL/api/v1/mcp-servers/sync/preview" \
  -H "Authorization: Bearer $TOKEN"
```

### 2. A2A Agents (via Admin API)

A2A agents are registered through the Admin API:

```bash
# List A2A agents
curl "$ADMIN_API_URL/api/v1/agents" \
  -H "Authorization: Bearer $TOKEN"
```

### 3. Workflow Engine

Run multi-step AI workflows using LangGraph templates (requires `--profile workflows`):

```bash
# List available workflow templates
curl http://localhost:8085/api/v1/templates

# Start a research workflow
curl -X POST http://localhost:8085/api/v1/executions \
  -H "Content-Type: application/json" \
  -d '{"template": "research", "input": {"query": "Latest trends in AI agents"}}'
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

LiteLLM is OpenAI-compatible, so any OpenAI SDK works out of the box.

### Python

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:4000/v1",
    api_key="$LITELLM_KEY"
)

# Chat with any model (OpenAI, Anthropic, Google, etc.)
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)

# Use model group aliases for automatic routing
response = client.chat.completions.create(
    model="fast",  # routes to cheapest fast model
    messages=[{"role": "user", "content": "What is 2+2?"}]
)
```

### JavaScript/TypeScript

```typescript
import OpenAI from 'openai';

const client = new OpenAI({
  baseURL: 'http://localhost:4000/v1',
  apiKey: '$LITELLM_KEY',
});

const response = await client.chat.completions.create({
  model: 'claude-sonnet-4.5',
  messages: [{ role: 'user', content: 'Explain the Gateway pattern.' }],
});
console.log(response.choices[0].message.content);
```

### curl

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "smart", "messages": [{"role": "user", "content": "Hello!"}]}'
```

## Architecture Diagrams

### Platform Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          Clients / Apps                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
       ┌──────▼──────┐ ┌────▼─────┐ ┌──────▼──────┐
       │  LiteLLM    │ │  Agent   │ │  Admin UI   │
       │  Port 4000  │ │  Gateway │ │  Port 5173  │
       │             │ │  Port 9000│ │  (React)    │
       │ • 100+ models│ │ • MCP    │ └──────┬──────┘
       │ • 9 providers│ │ • A2A    │        │
       │ • Cost track │ │ • Hot-   │ ┌──────▼──────┐
       └──────┬──────┘ │   reload │ │  Admin API  │
              │        └────▲─────┘ │  Port 8086  │
              │             │config  │  FastAPI    │
              │        ┌────┴─────┐ └──────┬──────┘
              │        │  Shared  │        │
              │        │  Volume  │        │
              │        └──────────┘        │
              │                            │
       ┌──────▼────────────────────────────▼──────┐
       │              PostgreSQL + Redis           │
       └───────────────────────────────────────────┘
```

## Monitoring

Start the observability stack with Docker Compose:

```bash
docker compose --env-file config/.env --profile observability up -d
```

| Service | URL | Purpose |
|---------|-----|---------|
| Grafana | http://localhost:3030 | Dashboards (admin / admin) |
| Prometheus | http://localhost:9090 | Metrics queries |
| Jaeger | http://localhost:16686 | Distributed tracing |

### Grafana Dashboards

- **AI Control Plane Overview** — requests, errors, latency, spend
- **FinOps Cost Tracking** — spend by model, team, and time

### Prometheus Queries

```promql
litellm_requests_metric_total
litellm_spend_metric_total
litellm_llm_api_latency_metric_bucket
```

## Troubleshooting

### Common Issues

1. **Service not healthy**
   ```bash
   docker compose ps
   docker compose logs <service-name> --tail 100
   ```

2. **LiteLLM returning 401**
   ```bash
   # Verify your API key matches config/.env
   grep LITELLM_MASTER_KEY config/.env
   ```

3. **Model returning errors**
   ```bash
   # Check provider API keys are set
   docker compose logs litellm --tail 50
   ```

4. **Agent Gateway not starting**
   ```bash
   # Agent Gateway requires --profile full
   docker compose --env-file config/.env --profile full up -d
   docker compose logs agentgateway --tail 50
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
- [Quickstart Guide](../docs/docs/guides/quickstart.md)
- [API Integration Guide](../docs/docs/guides/api-integration.md)
- [Cost Management Guide](../docs/docs/guides/cost-management.md)
- [Security Threat Model](../docs/security/threat-model.md)

## Contributing

See examples you'd like to add? Submit a PR!

1. Fork the repository
2. Create your example file
3. Add it to this README
4. Submit a pull request

## License

MIT License - see [LICENSE](../LICENSE) for details
