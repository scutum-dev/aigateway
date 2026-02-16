# Quickstart Guide

Get the AI Control Plane platform running locally in under 5 minutes.

## Prerequisites

- **Docker Desktop** (v4.0+) with Docker Compose v2
- At least one AI provider API key (OpenAI, Anthropic, Google, xAI, or DeepSeek)

No other dependencies are required. Everything runs inside containers.

## 1. Clone the Repository

```bash
git clone https://github.com/your-org/gateway.git
cd gateway
```

## 2. Configure API Keys

Open the environment file at `config/.env` and add your provider API keys:

```bash
# config/.env

# Required: At least one provider key
OPENAI_API_KEY=sk-proj-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key

# Optional: Additional providers
XAI_API_KEY=xai-your-xai-key
GOOGLE_API_KEY=your-google-key
DEEPSEEK_API_KEY=your-deepseek-key
```

The file already contains a default `LITELLM_MASTER_KEY` for local development. You will use this key to authenticate all API requests:

```
LITELLM_MASTER_KEY=$LITELLM_KEY
```

> **Important:** Change `LITELLM_MASTER_KEY` to a strong random value before any production or shared deployment.

## 3. Start the Platform

```bash
docker compose --env-file config/.env up -d
```

This starts the core services:

| Service    | URL                        | Purpose                    |
|------------|----------------------------|----------------------------|
| LiteLLM    | http://localhost:4000      | OpenAI-compatible API      |
| Admin API  | http://localhost:8086      | Configuration & management |
| Admin UI   | http://localhost:5173      | Web admin console          |
| Landing UI | http://localhost:9999      | Interactive playground     |
| Docs Site  | http://localhost:8089      | Developer documentation    |
| PostgreSQL | localhost:5432             | Database                   |
| Redis      | localhost:6379             | Cache                      |

Wait about 30 seconds for all health checks to pass:

```bash
docker compose ps
```

All services should show `healthy` or `running` status.

## 4. Send Your First Request

Make an OpenAI-compatible chat completion request to the LiteLLM proxy:

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [
      {"role": "user", "content": "Hello! What can you do?"}
    ]
  }'
```

You should receive a standard OpenAI-format JSON response with the model's reply.

### Try a Different Provider

Switch to Anthropic Claude with a single model name change:

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -d '{
    "model": "claude-haiku-4.5",
    "messages": [
      {"role": "user", "content": "Explain the Gateway pattern in one paragraph."}
    ]
  }'
```

### Try a Model Group Alias

Request the "fast" group, which automatically routes across the fastest models from all providers:

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -d '{
    "model": "fast",
    "messages": [
      {"role": "user", "content": "What is 2 + 2?"}
    ]
  }'
```

## 5. Open the Admin UI

Navigate to **http://localhost:5173** in your browser.

1. On the login screen, enter your master key: `$LITELLM_KEY`
2. Click **Sign In**
3. You will land on the **Dashboard** showing today's request count, cost, and model usage

From the sidebar, explore:
- **API Keys** -- generate and manage API keys with budgets and model restrictions
- **Models** -- see all 100+ configured models, filter by provider, edit routing tiers
- **Budgets** -- create spending limits for teams or users
- **Teams** -- organize users into teams with default models
- **MCP Servers** -- configure Model Context Protocol servers for tool access
- **Workflows** -- run and monitor LangGraph workflow templates
- **Settings** -- toggle caching, cost tracking, routing policies, and more

## 6. Explore the Playground

Open **http://localhost:9999** to access the interactive playground where you can test different models, compare responses, and experiment with parameters.

## Starting Additional Services

The default `docker compose up` starts only the core services. Use profiles to enable more:

```bash
# Add observability (Prometheus, Grafana, Jaeger)
docker compose --env-file config/.env --profile observability up -d

# Add workflow engine (Temporal, LangGraph workflows)
docker compose --env-file config/.env --profile workflows up -d

# Add FinOps services (cost predictor, budget webhook, reporter)
docker compose --env-file config/.env --profile finops up -d

# Start everything
docker compose --env-file config/.env --profile full up -d
```

## Stopping the Platform

```bash
docker compose --env-file config/.env down
```

Add `-v` to also remove persistent volumes (database data, cache):

```bash
docker compose --env-file config/.env down -v
```

## Troubleshooting

**Services not starting?** Check logs for a specific service:
```bash
docker compose logs litellm
docker compose logs admin-api
```

**LiteLLM returning 401?** Verify your `Authorization` header matches the `LITELLM_MASTER_KEY` value in `config/.env`.

**Model returning errors?** Ensure you have set the correct API key for that model's provider in `config/.env`. For example, Anthropic models require `ANTHROPIC_API_KEY`.

**Port conflicts?** Edit the port variables in `config/.env` (e.g., `LITELLM_PORT`, `ADMIN_UI_PORT`) to use different ports.

## Next Steps

- [API Integration Guide](./API_INTEGRATION.md) -- code examples in Python, TypeScript, Go, and curl
- [Model Routing Guide](./MODEL_ROUTING.md) -- understand how models are selected and routed
- [Cost Management Guide](./COST_MANAGEMENT.md) -- set up budgets, alerts, and cost optimization
- [Admin UI Guide](./ADMIN_GUIDE.md) -- detailed walkthrough of every admin console page
