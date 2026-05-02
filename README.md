# Scutum

A self-hosted *control plane* for AI infrastructure. Sits on top of [LiteLLM](https://docs.litellm.ai) (LLM proxy) and [Agent Gateway](https://agentgateway.dev) (MCP/A2A) and adds: unified Admin UI, DB-backed configuration, cost governance, audit, RBAC, workflow orchestration, semantic caching, guardrails, SRE agent for incident remediation, and FinOps reporting.

Run on your own cluster, your own keys, your own data. One OpenAI-compatible endpoint, 100+ models across 9 providers, with cost prediction, budget enforcement, Cedar-policy authorization, and a 7-year audit trail built in.

**Public site**: [scutum.dev](https://scutum.dev/) · **Docs**: [scutum.dev/docs](https://scutum.dev/docs/) · **Operated by**: Scuti Marketplace India (OPC) Pvt Ltd

**Core idea:** LiteLLM and Agent Gateway are powerful standalone tools. Scutum is the cockpit that ties them together with one UI, one database, one deployment pipeline — plus the cost/audit/policy machinery enterprises need on top.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            CLIENTS / APPS                               │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────┐
│                      Nginx Ingress (Port 80/443)                        │
│  /v1/* → LiteLLM  |  /mcp/* → Agent Gateway  |  /admin/* → Admin UI    │
└───────┬──────────────────────┬──────────────────────────┬──────────────┘
        │                      │                          │
┌───────▼───────┐    ┌────────▼────────┐        ┌───────▼────────┐
│   LiteLLM     │    │  Agent Gateway  │        │   Admin UI     │
│   Port 4000   │    │  Port 9000      │        │   Port 5173    │
│               │    │                 │        │   (React/Vite) │
│ • 100+ models │    │ • MCP backends  │        │                │
│ • 9 providers │    │ • A2A backends  │        │ • Models       │
│ • Cost track  │    │ • Hot-reload    │        │ • Keys/Teams   │
│ • Guardrails  │    │                 │        │ • MCP Servers  │
└───────┬───────┘    └────────▲────────┘        │ • A2A Agents   │
        │                     │ config sync      │ • Guardrails   │
        │              ┌──────┴───────┐         │ • Budgets      │
        │              │ Shared Volume│         │ • Workflows    │
        │              │ (config.yaml)│         │ • Settings     │
        │              └──────▲───────┘         └───────┬────────┘
        │                     │                         │
        │              ┌──────┴───────────────────────────┐
        │              │          Admin API               │
        │              │          Port 8086               │
        └──────────────┤                                  │
                       │ • JWT auth                       │
                       │ • CRUD for all config            │
                       │ • Gateway sync (MCP + A2A)       │
                       │ • Alembic migrations             │
                       └──────┬───────────────────────────┘
                              │
               ┌──────────────┼──────────────┐
               │              │              │
        ┌──────▼──────┐ ┌────▼────┐  ┌──────▼──────┐
        │ PostgreSQL  │ │  Redis  │  │  Workflow   │
        │             │ │         │  │  Engine     │
        │ • mcp_servers│ │ Cache   │  │  Port 8085  │
        │ • a2a_agents │ │ Rate    │  │  LangGraph  │
        │ • guardrails │ │ limit   │  │  + Temporal  │
        │ • settings  │ │         │  │             │
        └─────────────┘ └─────────┘  └─────────────┘
```

### Key Deployment Flow

```
Admin UI → Admin API → PostgreSQL (source of truth)
                    ↓
              gateway_sync.py
                    ↓
            Shared Volume (config.yaml)
                    ↓
         Agent Gateway (hot-reload)
              ├── MCP backends
              └── A2A backends
```

## Why This Platform?

### Before This Platform (LiteLLM + Agent Gateway separately)

| Task | What you do |
|------|-------------|
| Add an MCP server | Edit `config.yaml`, restart Agent Gateway |
| Add an A2A agent | Edit `config.yaml`, restart Agent Gateway |
| Change MCP + A2A together | Edit `config.yaml` carefully, restart |
| See which MCP servers are deployed | Read the YAML file |
| Track who changed what | Hope someone committed the diff |
| Run a multi-step AI workflow | Build it yourself |
| See combined LLM + agent costs | Check two dashboards separately |

### With This Platform

| Task | What you do |
|------|-------------|
| Add an MCP server | Click "Add Server" in Admin UI, Deploy to Gateway |
| Add an A2A agent | Click "Add Agent" in Admin UI, Deploy to Gateway |
| Change MCP + A2A together | Atomic deploy — both pushed to gateway config at once |
| See which servers/agents are deployed | Preview Config button shows exact YAML |
| Track who changed what | All config in Postgres with timestamps |
| Run a multi-step AI workflow | Pick a template (research/coding/data-analysis), click Run |
| See combined LLM + agent costs | Single Grafana dashboard |

## What This Platform Adds

Neither LiteLLM nor Agent Gateway provides these features alone:

| Feature | Description |
|---------|-------------|
| **Unified Admin UI** | One React app managing models, keys, teams, budgets, MCP servers, A2A agents, guardrails, workflows, and settings |
| **DB-Backed Gateway Config** | MCP servers and A2A agents stored in Postgres — survives config file loss, queryable, auditable |
| **Atomic Deploy** | MCP + A2A backends deployed together with one button click via `gateway_sync.py` |
| **Workflow Orchestration** | LangGraph templates + Temporal for durable multi-step AI workflows (research, coding, data-analysis) |
| **FinOps Suite** | Cost predictor, budget webhook (soft/hard limits), FinOps reporter with CSV/JSON export |
| **Pre-Built Dashboards** | Grafana dashboards combining LiteLLM spend data + Agent Gateway metrics |
| **Unified Auth** | Single JWT login across all admin operations |
| **Production K8s** | Kustomize manifests + Terraform (GCP GKE) for the full stack |

### What LiteLLM Already Handles (we don't duplicate)

LiteLLM v1.80+ has native support for: Admin UI, model management, API keys, teams/orgs, budgets, cost tracking, guardrails, MCP registry, A2A agent hub, prompt studio, and SSO. Our Admin API proxies LiteLLM's APIs for keys, teams, budgets, and models — providing a unified interface rather than reimplementing these features.

### What Agent Gateway Already Handles (we don't duplicate)

Agent Gateway v0.12+ has: MCP federation, A2A routing, LLM inference proxy, built-in admin UI (port 15000), JWT/OAuth/mTLS auth, CEL-based authorization, prompt guards, tool poisoning protection, and hot-reload. We use its file-watcher for config hot-reload and its MCP/A2A protocol handling.

## Components

| Component | Port | Description |
|-----------|------|-------------|
| **LiteLLM** | 4000 | LLM proxy — 100+ models, cost tracking, provider routing |
| **Agent Gateway** | 9000 | MCP + A2A protocol proxy, tool federation, hot-reload |
| **Admin API** | 8086 | FastAPI — JWT auth, CRUD, gateway sync |
| **Admin UI** | 5173 | React — unified management dashboard |
| **Workflow Engine** | 8085 | LangGraph + Temporal — multi-step AI workflows |
| **Cost Predictor** | 8080 | Per-request cost estimation |
| **Budget Webhook** | 8081 | Soft/hard budget enforcement with alerts |
| **PostgreSQL** | 5432 | Source of truth for all config |
| **Redis** | 6379 | Caching, rate limiting |
| **Prometheus** | 9090 | Metrics collection |
| **Grafana** | 3030 | Dashboards and visualization |
| **Jaeger** | 16686 | Distributed tracing |

## Customer install (one-liner)

If you have a license JWT and want to deploy Scutum on a Linux server (cloud VM, on-prem box, k8s host):

```bash
curl -fsSL https://scutum.dev/install.sh | sh
cd scutum
# Edit config/.env — paste LICENSE_KEY + at least one provider API key
./scutum up
```

The installer:

- Verifies you have **Docker Engine 20.10+** *or* **Podman 4.4+** (no Docker Desktop required — your install runs on Apache 2.0 components, no Docker Inc commercial license).
- Drops a slim `docker-compose.yaml` referencing pre-built images on **GHCR** (no source code, no `build:` directives).
- Creates `config/.env` from a template **and generates fresh random secrets** so production never ships with default keys.
- Bundles the Scutum license public key for offline JWT validation.
- Drops a `scutum` CLI wrapper covering `up / down / logs / ps / pull / upgrade / backup / restore / activate / license`.

Optional bundles via Compose profiles:

```bash
./scutum up --profile sre              # LLM-driven incident remediation
./scutum up --profile finops           # Cost prediction + budget enforcement
./scutum up --profile observability    # Prometheus + Grafana + Jaeger
./scutum up --profile full             # everything
```

Customer never clones the repo. Upgrades are `./scutum upgrade 0.2.0`. Compose-spec compatible — the same `docker-compose.yaml` works under `podman-compose` and `nerdctl compose`.

## Developer Quick Start (this repo)

### Prerequisites

- Docker & Docker Compose
- API keys for at least one provider (OpenAI, Anthropic, etc.)

### Setup

```bash
cd gateway
cp config/.env.example config/.env
# Edit config/.env — add your API keys
```

### Start

```bash
# Customer-safe core (postgres, redis, litellm, admin-api, admin-ui, docs)
make up

# Add observability (Grafana, Prometheus, Jaeger)
make up-observability

# Add workflows (Temporal, LangGraph engine, A2A runtime)
make up-workflows

# Add FinOps (cost predictor, budget webhook)
make up-finops

# Add SRE agent (LLM-driven incident remediation, human-in-loop)
make up-sre

# Everything (including agent gateway, vault, marketing surfaces)
make up-full
```

> **Customer vs scutum.dev internal**: `make up` is customer-safe — it omits the
> scutum.dev marketing surfaces (landing page, Cal.com Book-a-Demo backend, sales
> deck, public playground). Those services are gated behind the `marketing`
> profile and only get spun up via `make up-marketing` for the scutum.dev VM.
> See [CLAUDE.md](./CLAUDE.md) for the boundary rule.

### Access

| Service | URL |
|---------|-----|
| Admin UI | http://localhost:5173 |
| LiteLLM API | http://localhost:4000 |
| Agent Gateway | http://localhost:9000 |
| Agent Gateway UI | http://localhost:15000 |
| Grafana | http://localhost:3030 |
| Jaeger | http://localhost:16686 |

### Test

```bash
# Login to Admin API
curl http://localhost:8086/auth/login \
  -H "Content-Type: application/json" \
  -d '{"api_key": "$LITELLM_KEY"}'

# LLM request via LiteLLM
curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "Hello!"}]}'
```

## Licensing

Scutum is **commercial self-hosted** software. Every deploy needs a license JWT
issued by us. The validation is **offline** — no phone-home — so once a license
is on the box, no outbound network is required to keep running.

```bash
# 1. Set LICENSE_KEY in config/.env to the JWT we sent you
echo "LICENSE_KEY=eyJhbGciOiJFZERTQSI..." >> config/.env

# 2. Bring up the platform — admin-api validates on startup
make up

# 3. Check the live license state
curl http://localhost:8086/api/v1/license | jq
```

If the license is expired, missing, or tampered with, admin-api **still boots**
(no hard kill) but `GET /api/v1/license` returns `valid:false` and the Admin UI
shows a renewal banner. Hard tier-gating is on the v2 roadmap.

To activate a refreshed license without restarting:

```bash
curl -X POST http://localhost:8086/api/v1/license/activate \
  -H "Authorization: Bearer <admin-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"license_key": "<new-jwt>"}'
```

**For Scutum operators only** — to mint a new trial license:

```bash
# Requires ~/.scutum/license-private.pem on your laptop (gitignored)
python scripts/issue-license.py \
  --email founder@acme.com --company "Acme Corp" --tier trial --days 30
```

## Admin API Reference

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/login` | Authenticate with API key |
| GET/POST | `/api/v1/mcp-servers` | MCP server CRUD |
| PUT/DELETE | `/api/v1/mcp-servers/{id}` | Update/delete MCP server |
| POST | `/api/v1/mcp-servers/{id}/test` | Test MCP server connectivity |
| POST | `/api/v1/mcp-servers/sync` | Deploy MCP + A2A config to gateway |
| GET | `/api/v1/mcp-servers/sync/preview` | Preview gateway config YAML |
| GET/POST | `/api/v1/agents` | A2A agent CRUD |
| PUT/DELETE | `/api/v1/agents/{id}` | Update/delete A2A agent |
| POST | `/api/v1/agents/{id}/test` | Test A2A agent connectivity |
| GET/POST | `/api/v1/models` | Model management (proxied to LiteLLM) |
| GET/POST | `/api/v1/keys` | API key management (proxied to LiteLLM) |
| GET/POST | `/api/v1/teams` | Team management (proxied to LiteLLM) |
| GET/POST | `/api/v1/budgets` | Budget management (proxied to LiteLLM) |
| GET/POST | `/api/v1/guardrails` | Guardrail config CRUD |
| GET/PUT | `/api/v1/settings` | Platform settings |
| GET | `/api/v1/reports/summary` | Cost dashboard data |
| GET/POST | `/api/v1/workflows` | Workflow templates |

## Docker Compose Profiles

| Profile | Services Added |
|---------|----------------|
| *(default)* | postgres, redis, litellm, admin-api, admin-ui, landing-ui, deck-ui, docs-site, playground-ui |
| `observability` | otel-collector, prometheus, grafana, jaeger |
| `workflows` | temporal, temporal-ui, workflow-engine, a2a-runtime |
| `finops` | cost-predictor, budget-webhook |
| `local-models` | gpu-stub (Ollama compatibility) |
| `infra` | vault, nginx |
| `full` | everything above + agent gateway |

## Supported Models

### Direct Providers
| Provider | Models |
|----------|--------|
| **OpenAI** | GPT-5, GPT-5.2, GPT-5-mini, o3, o3-pro, o4-mini, GPT-4o, GPT-4o-mini |
| **Anthropic** | Claude Opus 4.5, Claude Sonnet 4.5, Claude Haiku 4.5, Claude Opus 4, Claude Sonnet 4 |
| **Google** | Gemini 3 Pro, Gemini 3 Flash, Gemini 2.5 Pro/Flash/Flash-Lite |
| **xAI** | Grok 4, Grok 4 Heavy, Grok 3, Grok 3 Mini |
| **DeepSeek** | DeepSeek V3, DeepSeek R1, DeepSeek Coder |

### Cloud Platforms
| Provider | Models |
|----------|--------|
| **AWS Bedrock** | Claude 4.5, Llama 4, Llama 3.x, Mistral, Nova, Titan, DeepSeek, Cohere, AI21 |
| **Google Vertex AI** | Gemini 3/2.5, Claude on Vertex, DeepSeek on Vertex |
| **Azure OpenAI** | GPT-5.x, GPT-4.1, o-series, GPT-4o, embeddings, audio |
| **Ollama** | Llama 3.1 (70B/8B), Mistral, CodeLlama |

### Model Groups

Semantic aliases for capability-based routing:
- `fast` — GPT-5-mini, Claude Haiku 4.5, Gemini 3 Flash, Grok 3 Mini
- `smart` — GPT-5, Claude Sonnet 4.5, Gemini 3 Pro, Grok 4
- `powerful` — GPT-5.2, Claude Opus 4.5, o3-pro, Grok 4 Heavy
- `reasoning` — o3, o3-pro, DeepSeek R1
- `coding` — Claude Sonnet 4.5, DeepSeek Coder, CodeLlama
- `cost-effective` — GPT-5-mini, Claude Haiku 4.5, Gemini 2.5 Flash-Lite, DeepSeek V3

## Cloud Deployment

### GCP (Terraform)

```bash
make demo           # Deploy demo environment
make staging        # Deploy staging environment
make prod           # Deploy production (requires confirmation)
make demo-destroy   # Tear down demo
```

### Kubernetes (Kustomize)

```bash
kubectl apply -k kubernetes/overlays/dev
kubectl apply -k kubernetes/overlays/staging
kubectl apply -k kubernetes/overlays/production
```

## Documentation

| Guide | Description |
|-------|-------------|
| [Quickstart](docs/docs/guides/quickstart.md) | Get running in 5 minutes |
| [API Integration](docs/docs/guides/api-integration.md) | Python, TypeScript, Go, curl examples |
| [Cost Management](docs/docs/guides/cost-management.md) | Budgets, alerts, FinOps |
| [Comparison](docs/docs/guides/comparison.md) | How we compare to alternatives |
| [LiteLLM Deep Dive](docs/docs/guides/litellm-integration.md) | What we use, what we don't |
| [Agent Gateway Deep Dive](docs/docs/guides/agentgateway-integration.md) | Integration details |
| [Admin Guide](docs/docs/guides/admin-guide.md) | UI walkthrough |

## References

- [Agent Gateway](https://agentgateway.dev) — Linux Foundation project for agentic AI connectivity
- [LiteLLM](https://docs.litellm.ai) — Open-source LLM proxy
- [LangGraph](https://langchain-ai.github.io/langgraph/) — Workflow orchestration
- [Temporal](https://temporal.io) — Durable execution engine
- [OpenTelemetry](https://opentelemetry.io) — Observability framework

## License

MIT License
