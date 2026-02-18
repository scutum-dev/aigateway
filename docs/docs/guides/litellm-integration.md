# LiteLLM Integration

How the AI Control Plane uses LiteLLM, which features are pre-configured and exposed through the Admin UI, and which features are available for adoption.

## Our Approach

LiteLLM v1.80+ has dozens of powerful features. Most deployments use less than 20% of them because configuration is complex, scattered across YAML files, and undocumented for specific use cases. This platform **pre-wires the most valuable features** with sensible defaults and exposes them through a unified UI.

### What We Pre-Configure

| Feature | LiteLLM Config | Platform Value-Add |
|---------|---------------|--------------------|
| **85+ models across 9 providers** | `model_list` in config.yaml | Pre-configured with pricing, RPM/TPM limits, and cross-provider fallback chains |
| **Usage-based routing** | `router_settings.routing_strategy` | Pre-set with RPM/TPM limit checking and pre-call validation |
| **Fallback chains** | `fallbacks` in config.yaml | Pre-built cross-provider chains (GPT-5 → Claude → Grok, etc.) |
| **Model group aliases** | Model groups in config.yaml | 15 semantic aliases: `fast`, `smart`, `powerful`, `reasoning`, `coding`, `cost-effective` + per-provider (`openai`, `anthropic`, `google`, `xai`, `deepseek`, `bedrock`, `vertex`, `azure`, `local`) |
| **Redis semantic caching** | `cache_params` | Pre-configured with `redis-semantic` type, 0.92 similarity threshold, 1-hour TTL |
| **OpenTelemetry + Prometheus** | `success_callback`, `failure_callback` | Pre-wired to OTEL collector + Prometheus, feeding pre-built Grafana dashboards |
| **Guardrails** | `guardrails` in config.yaml | Custom pre-call guardrail handler, manageable via Admin UI |
| **Budget defaults** | `budget_config` | Global soft/hard limits + per-key defaults, plus budget webhook for alerts |
| **Health checks** | `background_health_checks` | Every 2 hours, auto-excludes unhealthy models from routing |
| **Retry with backoff** | `retry_policy` | 3 retries with exponential backoff before fallback chain triggers |

### What the Admin UI Exposes

These LiteLLM features are fully manageable through our React dashboard:

| Admin UI Page | LiteLLM Feature | What You Can Do |
|---------------|-----------------|-----------------|
| **Models** | `/model/info`, `/model/new`, `/model/delete` | View all models, add new ones, delete unused |
| **API Keys** | `/key/generate`, `/key/info`, `/key/delete` | Create keys with budgets, rate limits, model restrictions, expiry |
| **Teams** | `/team/new`, `/team/update`, `/team/delete` | Create teams with isolated budgets and model access |
| **Budgets** | `/budget/new`, `/budget/info` | Create reusable budget profiles |
| **Guardrails** | Custom CRUD in Admin API | Toggle PII detection, prompt injection, toxicity per configuration |
| **Settings** | Platform settings table | Default model, global rate limit, caching, maintenance mode |
| **Dashboard** | `/spend/report` | Today/week/month spend, top models, request counts |

## LiteLLM Features We Surface

### Cost Tracking & FinOps

LiteLLM tracks spend per request automatically. We build on this with:

- **Dashboard page** — real-time cost/request/token charts
- **Budget webhook** — soft limits trigger Slack/PagerDuty/email alerts, hard limits block requests
- **Cost predictor** — per-request cost estimates using tiktoken + model pricing tables
- **Grafana dashboards** — FinOps cost tracking dashboard with trend analysis

### Guardrails

LiteLLM v1.79+ has built-in content filtering (PII, bias, toxicity). We expose this through:

- **Admin UI guardrails page** — create named configurations with toggles for each scanner
- **Per-team assignment** — assign different guardrail configs to different teams
- **Event logging** — guardrail violations logged with risk scores and actions taken

### Observability

LiteLLM emits OTEL traces and Prometheus metrics. We pre-wire:

- **OTEL Collector** — receives traces from LiteLLM + Agent Gateway + Admin API
- **Prometheus** — scrapes metrics from all services
- **Grafana** — pre-built dashboards for platform overview, FinOps, infrastructure
- **Jaeger** — distributed tracing UI for debugging request flows

### Caching

LiteLLM supports multiple cache types. Pre-configured with semantic caching:

```yaml
cache: true
cache_params:
  type: "redis-semantic"
  host: "redis"
  port: 6379
  ttl: 3600
  namespace: "litellm"
  similarity_threshold: 0.92
  redis_semantic_cache_embedding_model: "text-embedding-3-small"
```

This caches responses by embedding similarity, so paraphrased prompts return cached results. Toggled on/off via Admin UI Settings page (`enable_caching`). See the [Semantic Caching Guide](./semantic-caching.md) for details.

---

## Additional LiteLLM Features

LiteLLM has additional native features beyond what we pre-configure. Some we already cover through the Admin API; others are available to enable directly.

### Already Covered by the Admin API

These LiteLLM features have equivalents built into the platform — no additional configuration or Enterprise license needed:

| LiteLLM Feature | Our Equivalent (Admin API) |
|---------|-------------|
| **Prompt Studio** | Prompt registry with versioning, rendering, and approval workflows (`/api/v1/prompts`) |
| **MCP permission management** | MCP server CRUD with connectivity testing and Agent Gateway deployment (`/api/v1/mcp-servers`) |
| **Granular RBAC** (Enterprise) | Cedar policies + org member roles + model access tiers with approval workflows (`/api/v1/model-access/tiers`) |
| **SSO** (Enterprise) | Full OIDC SSO per organization (`/api/v1/organizations/{org_id}/sso`) — Okta, Google, Azure AD |
| **Per-team guardrails** (Enterprise) | Guardrail configs assigned per team (`/api/v1/guardrails/{id}/assign/{team_id}`) |
| **Tag budgets** (Enterprise) | Team budgets + cost allocation rules with cost centers (`/api/v1/cost-allocation/rules`) |
| **Audit logs** (Enterprise) | Filterable audit logs with CSV/JSON export (`/api/v1/audit-logs`) |
| **Dynamic rate limiter** (Enterprise) | Per-user/team/model rate policies with burst multipliers and pre-flight checks (`/api/v1/rate-limits`) |

### Available to Enable (LiteLLM native)

These LiteLLM-native features are not yet exposed in the platform but can be enabled with minimal effort:

| Feature | Effort | Value |
|---------|--------|-------|
| **Semantic caching (Qdrant)** | Config change | Alternative to Redis semantic caching using Qdrant vector DB |
| **Slack/Discord alerting** | Config change | Real-time alerts for slow responses, error spikes, budget thresholds |
| **Tag-based routing** | Config change | Route requests by metadata (production vs dev, priority tiers) |
| **Pass-through endpoints** | Config change | Direct provider API access with cost tracking |
| **Langfuse integration** | Add callback + deploy Langfuse | Prompt tracing, evaluation, and analytics |
| **Batch API** | Enable endpoint | 50% cost reduction for bulk processing |
| **Traffic mirroring** | Config change | Shadow production traffic to evaluate new models |
| **Key rotation** | Config + secret manager | Automatic credential rotation |

---

## Configuration Reference

### Model Routing

From `config/litellm/config.yaml`:

```yaml
router_settings:
  routing_strategy: "usage-based-routing"
  routing_strategy_args:
    ttl: 60
    rpm_limit_check: true
    tpm_limit_check: true
  enable_pre_call_checks: true
```

### Fallback Chains

```yaml
fallbacks:
  - "gpt-5": ["gpt-5.2", "claude-opus-4.5", "grok-4"]
  - "claude-opus-4.5": ["claude-sonnet-4.5", "gpt-5", "grok-4"]
  - "gemini-3-pro": ["gemini-2.5-pro", "claude-sonnet-4.5", "gpt-5"]
```

### Budget Configuration

```yaml
budget_config:
  global_budget:
    soft_budget: 1000.00
    max_budget: 1500.00
    budget_duration: "monthly"
  default_key_config:
    max_budget: 100.00
    budget_duration: "monthly"
    rpm_limit: 100
    tpm_limit: 100000
```

### Observability Callbacks

```yaml
litellm_settings:
  success_callback: ["otel", "prometheus"]
  failure_callback: ["otel", "prometheus"]
  service_callback: ["prometheus"]
```

---

## Migration from Standalone LiteLLM

If you're already running LiteLLM standalone:

### Step 1: Merge Your Config

The platform's `config/litellm/config.yaml` uses the same format. Add your custom models alongside the 85+ pre-configured ones.

### Step 2: Set Environment Variables

Move API keys to `config/.env`:

```bash
cp config/.env.example config/.env
# Add: OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.
```

### Step 3: Start the Platform

```bash
docker compose up -d
```

Your existing OpenAI-compatible client code doesn't change:

```python
client = OpenAI(base_url="http://localhost:4000/v1", api_key="sk-...")
```

### Step 4: Enable Additional Services

```bash
docker compose --profile observability up -d  # Grafana, Prometheus, Jaeger
docker compose --profile finops up -d          # Cost predictor, budget webhook
docker compose --profile workflows up -d       # Temporal, LangGraph
```

---

## Integrating with an Existing LiteLLM Instance

If you already run LiteLLM in production and want to add the platform's governance, FinOps, and UI features without replacing your existing proxy, you can point the platform at your running instance instead of using the bundled one.

### What Changes

The bundled `litellm` container is replaced by your existing deployment. All platform services that talk to LiteLLM (Admin API, workflow engine, cost predictor, budget webhook, A2A runtime) are redirected to your instance via environment variables.

### Step 1: Set Environment Variables

In `config/.env`, point to your existing LiteLLM:

```bash
# Your existing LiteLLM instance
LITELLM_URL=https://litellm.internal.example.com:4000
LITELLM_MASTER_KEY=sk-your-existing-master-key
```

### Step 2: Disable the Bundled LiteLLM Service

Create a `docker-compose.override.yaml` in the project root:

```yaml
services:
  litellm:
    profiles: ["disabled"]  # Prevents this service from starting

  admin-api:
    environment:
      LITELLM_URL: ${LITELLM_URL}
      LITELLM_MASTER_KEY: ${LITELLM_MASTER_KEY}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
      # Remove litellm dependency — the override replaces the entire depends_on

  workflow-engine:
    environment:
      LITELLM_URL: ${LITELLM_URL}
      LITELLM_API_KEY: ${LITELLM_MASTER_KEY}
    depends_on:
      postgres:
        condition: service_healthy
      # Remove litellm dependency

  a2a-runtime:
    environment:
      LITELLM_URL: ${LITELLM_URL}

  cost-predictor:
    environment:
      LITELLM_URL: ${LITELLM_URL}

  budget-webhook:
    environment:
      LITELLM_URL: ${LITELLM_URL}
```

### Step 3: Ensure Network Connectivity

Your existing LiteLLM must be reachable from the Docker network. Options:

- **Same Docker network**: Add `external: true` to `gateway-network` and connect your LiteLLM container.
- **Host network**: Use `host.docker.internal` (macOS/Windows) or `172.17.0.1` (Linux) if LiteLLM runs on the host.
- **Remote**: Use the full URL (e.g., `https://litellm.internal.example.com:4000`). Ensure the Docker containers can reach it.

### Step 4: Verify

```bash
docker compose --env-file config/.env up -d

# Confirm Admin API can reach your LiteLLM
curl http://localhost:8086/health
# Should return {"status": "ok"}

# Confirm models are visible through the Admin API
TOKEN=$(curl -s http://localhost:8086/auth/login \
  -d '{"api_key":"sk-your-existing-master-key"}' \
  -H 'Content-Type: application/json' | jq -r .access_token)

curl http://localhost:8086/api/v1/models \
  -H "Authorization: Bearer $TOKEN" | jq length
```

### What Works

All platform features work with an external LiteLLM instance:

| Feature | Status | Notes |
|---------|--------|-------|
| Admin UI dashboard | Works | Reads spend/metrics from LiteLLM's API |
| Model/key/team management | Works | Proxies to your LiteLLM's `/model/*`, `/key/*`, `/team/*` |
| Guardrails | Works | Configured via Admin API, applied via LiteLLM's guardrail hooks |
| FinOps (cost prediction, budgets) | Works | Cost predictor calls your LiteLLM for model info |
| Workflows | Works | Workflow engine sends LLM calls to your LiteLLM |
| Semantic caching | Depends | Uses your LiteLLM's cache config — ensure `redis-semantic` is configured |
| Observability | Partial | Platform dashboards work if your LiteLLM emits Prometheus metrics to the same endpoint |

### What Does Not Work

- **Config file management**: The platform cannot edit your LiteLLM's `config.yaml`. Model definitions, fallback chains, and router settings must be managed in your existing config.
- **Health-gated startup**: The bundled setup waits for LiteLLM to be healthy before starting the Admin API. With an external instance, services start immediately — ensure your LiteLLM is already running.

---

## Related Guides

- [Comparison](./comparison.md) — how the platform compares to alternatives
- [Agent Gateway Deep Dive](./agentgateway-integration.md) — Agent Gateway integration
- [Cost Management](./cost-management.md) — budgets and FinOps
