# LiteLLM Integration

How the AI Control Plane uses LiteLLM, which features are pre-configured and exposed through the Admin UI, and which features are available for adoption.

## Our Approach

LiteLLM v1.80+ has dozens of powerful features. Most deployments use less than 20% of them because configuration is complex, scattered across YAML files, and undocumented for specific use cases. This platform **pre-wires the most valuable features** with sensible defaults and exposes them through a unified UI.

### What We Pre-Configure

| Feature | LiteLLM Config | Platform Value-Add |
|---------|---------------|--------------------|
| **100+ models across 9 providers** | `model_list` in config.yaml | Pre-configured with pricing, RPM/TPM limits, and cross-provider fallback chains |
| **Usage-based routing** | `router_settings.routing_strategy` | Pre-set with RPM/TPM limit checking and pre-call validation |
| **Fallback chains** | `fallbacks` in config.yaml | Pre-built cross-provider chains (GPT-5 → Claude → Grok, etc.) |
| **Model group aliases** | Model groups in config.yaml | 12 semantic aliases: `fast`, `smart`, `powerful`, `reasoning`, `coding`, `cost-effective` + per-provider |
| **Redis caching** | `cache_params` | Pre-configured with 1-hour TTL and namespacing |
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

LiteLLM supports Redis exact-match caching. Pre-configured with:

```yaml
cache: true
cache_params:
  type: "redis"
  host: "redis"
  port: 6379
  ttl: 3600
  namespace: "litellm"
```

Toggled on/off via Admin UI Settings page (`enable_caching`).

---

## Features Available for Adoption

LiteLLM has features we haven't yet exposed in the platform. These are ready to enable:

### High-Impact, Easy to Enable

| Feature | Effort | Value |
|---------|--------|-------|
| **Semantic caching (Qdrant)** | Config change | Similar prompts return cached responses — significant cost savings |
| **Prompt Studio** | Use LiteLLM's built-in UI at `/ui` | Prompt versioning and testing without code changes |
| **Slack/Discord alerting** | Config change | Real-time alerts for slow responses, error spikes, budget thresholds |
| **Tag-based routing** | Config change | Route requests by metadata (production vs dev, priority tiers) |
| **Pass-through endpoints** | Config change | Direct provider API access with cost tracking |

### Medium-Impact, Moderate Effort

| Feature | Effort | Value |
|---------|--------|-------|
| **Langfuse integration** | Add callback + deploy Langfuse | Prompt tracing, evaluation, and analytics |
| **Batch API** | Enable endpoint | 50% cost reduction for bulk processing |
| **Traffic mirroring** | Config change | Shadow production traffic to evaluate new models |
| **Key rotation** | Config + secret manager | Automatic credential rotation |
| **MCP permission management** | Config change | Per-key/team/org control over which MCP tools are accessible |

### Enterprise Tier (LiteLLM license required)

| Feature | What It Adds |
|---------|-------------|
| **Granular RBAC** | Role-based permissions beyond admin/user |
| **SSO (6+ users)** | Okta, Google, Azure AD integration |
| **Per-team guardrails** | Different guardrail configs per team (native) |
| **Tag budgets** | USD budgets on custom request tags |
| **Audit logs** | Compliance-grade activity logging |
| **Dynamic rate limiter** | Automatic throughput optimization |

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

The platform's `config/litellm/config.yaml` uses the same format. Add your custom models alongside the 100+ pre-configured ones.

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

## Related Guides

- [Comparison](./comparison.md) — how the platform compares to alternatives
- [Agent Gateway Deep Dive](./agentgateway-integration.md) — Agent Gateway integration
- [Cost Management](./cost-management.md) — budgets and FinOps
