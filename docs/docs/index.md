# AI Control Plane Platform

Unified AI infrastructure for the enterprise. One API, 100+ models, 9 providers, intelligent routing, and complete cost visibility.

---

## What is the AI Control Plane?

The AI Control Plane is a self-hosted platform that sits between your applications and AI providers (OpenAI, Anthropic, Google, xAI, DeepSeek, AWS Bedrock, Azure, Vertex AI, Ollama). Every request flows through a single OpenAI-compatible API endpoint, giving you:

- **Provider abstraction** — switch models with a one-word change, no code rewrites
- **Intelligent routing** — automatic failover, load balancing, and policy-based model selection
- **Cost management** — real-time spend tracking, per-team budgets, and alerts
- **Enterprise controls** — RBAC, rate limiting, audit logging, and Cedar policy engine

## Quick Links

| Guide | Description |
|-------|-------------|
| [Quickstart](guides/quickstart.md) | Get running locally in under 5 minutes |
| [API Integration](guides/api-integration.md) | Code examples in Python, TypeScript, Go, and curl |
| [Model Routing](guides/model-routing.md) | How models are selected, fallback chains, and group aliases |
| [Cost Management](guides/cost-management.md) | Budgets, alerts, FinOps reporting, and optimization tips |
| [Admin Guide](guides/admin-guide.md) | Page-by-page walkthrough of the Admin Console |

## Architecture Overview

```
Your App ──▶ AI Control Plane (LiteLLM) ──▶ OpenAI / Anthropic / Google / xAI / DeepSeek / Bedrock / Azure / Vertex / Ollama
                 │
                 ├── Agent Gateway (MCP + A2A protocols)
                 ├── Policy Router (Cedar rules)
                 ├── Semantic Cache (Redis + embeddings)
                 ├── Cost Predictor (per-request estimates)
                 ├── Budget Webhook (soft/hard limits)
                 ├── FinOps Reporter (CSV/JSON exports)
                 ├── Workflow Engine (LangGraph templates)
                 ├── A2A Runtime (Temporal agent workflows)
                 └── Admin API + UI (configuration & monitoring)
```

## Default Services

Start the platform with `docker compose --env-file config/.env up -d`:

| Service | URL | Purpose |
|---------|-----|---------|
| LiteLLM | [localhost:4000](http://localhost:4000) | OpenAI-compatible LLM proxy |
| Admin UI | [localhost:5173](http://localhost:5173) | Web admin console |
| Landing Page | [localhost:9999](http://localhost:9999) | Interactive demo & playground |
| Docs Site | [localhost:8089](http://localhost:8089) | Developer documentation |
| Admin API | [localhost:8086](http://localhost:8086) | REST management API |

### Production URLs

| Service | URL |
|---------|-----|
| LLM API | `https://api.aicontrolplane.dev` |
| Admin Console | `https://api.aicontrolplane.dev/admin` |
| Developer Docs | `https://docs.aicontrolplane.dev` |

## Model Groups

Request a group alias and the gateway picks the best available model:

| Alias | Models | Best For |
|-------|--------|----------|
| `fast` | gpt-5-mini, claude-haiku-4.5, gemini-3-flash, grok-3-mini | Low-latency responses |
| `smart` | gpt-5, claude-sonnet-4.5, gemini-3-pro, grok-4 | Balanced quality & speed |
| `powerful` | gpt-5.2, claude-opus-4.5, o3-pro, grok-4-heavy | Maximum capability |
| `reasoning` | o3, o3-pro, deepseek-r1 | Complex multi-step reasoning |
| `coding` | claude-sonnet-4.5, deepseek-coder, codellama | Code generation & review |
| `cost-effective` | gpt-5-mini, claude-haiku-4.5, gemini-2.5-flash-lite, deepseek-v3 | Budget-friendly |

```bash
# One API, any model
curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "smart", "messages": [{"role": "user", "content": "Hello!"}]}'
```
