# Comparison with Alternatives

How the AI Control Plane compares to other AI gateway and infrastructure products.

## Overview

The AI gateway market is growing rapidly as enterprises adopt multi-model AI strategies. Here's how the AI Control Plane compares to the leading alternatives across key dimensions.

## Feature Comparison

| Feature | AI Control Plane | Solo.io AI Gateway | Kong AI Gateway | Portkey | LiteLLM (standalone) | Helicone |
|---------|-----------------|-------------------|-----------------|---------|---------------------|----------|
| **OpenAI-compatible API** | Yes | Yes | Yes | Yes | Yes | Proxy only |
| **Multi-provider routing** | 9 providers, 100+ models | Limited providers | Via plugins | 5+ providers | 100+ providers | Logging only |
| **Automatic failover** | Built-in fallback chains | Manual config | Manual config | Built-in | Built-in | No |
| **Model group aliases** | Yes (fast, smart, powerful) | No | No | No | Custom groups | No |
| **Cost tracking** | Real-time, per-key/team | Basic | Via plugin | Yes | Built-in | Yes |
| **Budget enforcement** | Soft + hard limits | No | No | Basic | Per-key limits | No |
| **Semantic caching** | Embedding similarity | No | No | Simple cache | Redis exact match | No |
| **MCP tool integration** | Full (stdio + http) | No | No | No | No | No |
| **Workflow orchestration** | LangGraph + Temporal | No | No | No | No | No |
| **Policy engine** | Cedar (RBAC + routing) | Envoy policies | Kong policies | No | No | No |
| **Admin UI** | Full-featured React app | Gloo UI | Kong Manager | Dashboard | Basic UI | Dashboard |
| **Grafana dashboards** | 2 pre-built | Custom | Custom | Built-in | No | Built-in |
| **Self-hosted** | Yes (Docker/K8s) | Yes | Yes | Cloud + self-host | Yes | Cloud + self-host |
| **Open source** | Yes | Partial (Gloo Edge OSS) | Partial (Kong OSS) | Partial | Yes (MIT) | Partial |
| **A2A protocol support** | Yes (agent-to-agent) | No | No | No | No | No |

## Detailed Comparisons

### vs. Solo.io AI Gateway (Gloo)

Solo.io's AI Gateway is built on Envoy proxy and Gloo Edge, targeting enterprises already in the Istio/Envoy ecosystem.

**Where Solo.io is stronger:**
- Deep Envoy/Istio integration and service mesh support
- Enterprise support contracts and SLAs
- Mature traffic management (canary, circuit breaking, mTLS)

**Where AI Control Plane is stronger:**
- Purpose-built for AI workloads (not a general API gateway with AI bolted on)
- Semantic caching with embedding similarity (not just exact match)
- MCP tool integration for agent workflows
- LangGraph/Temporal workflow orchestration
- Built-in FinOps with Grafana dashboards and budget enforcement
- 100+ pre-configured models across 9 providers
- No Envoy/Istio dependency

**Best for:** Solo.io if you're already running Istio and need AI capabilities within your service mesh. AI Control Plane if you want a dedicated AI infrastructure layer.

### vs. Kong AI Gateway

Kong's AI Gateway adds LLM proxy capabilities to the Kong API gateway via plugins.

**Where Kong is stronger:**
- Massive API gateway ecosystem with 100+ plugins
- Battle-tested at scale for general API traffic
- Enterprise features (developer portal, API analytics)

**Where AI Control Plane is stronger:**
- Native multi-model routing with fallback chains (not plugin-based)
- Semantic caching (Kong has no equivalent)
- MCP server management and Agent Gateway
- Workflow orchestration (Kong has no equivalent)
- Cedar policy engine for AI-specific routing rules
- Dedicated cost management with soft/hard budget limits
- Lighter footprint (no Lua/OpenResty stack)

**Best for:** Kong if you're already a Kong shop and want to add AI proxying to your existing gateway. AI Control Plane if AI is the primary use case.

### vs. Portkey

Portkey is a cloud-native AI gateway focused on observability and reliability.

**Where Portkey is stronger:**
- Polished cloud-hosted option (no infrastructure to manage)
- Built-in prompt management and versioning
- A/B testing for prompts
- Faster onboarding for small teams

**Where AI Control Plane is stronger:**
- Fully self-hosted (no data leaves your infrastructure)
- Semantic caching with configurable similarity thresholds
- MCP tool integration and Agent Gateway
- Workflow orchestration (LangGraph + Temporal)
- Cedar policy engine for fine-grained access control
- More comprehensive budget enforcement (soft + hard limits, per-team)
- No per-request pricing

**Best for:** Portkey if you want a managed cloud service. AI Control Plane if you need self-hosted control over your AI infrastructure.

### vs. LiteLLM (standalone)

The AI Control Plane uses LiteLLM as its core proxy engine, so this is a comparison of the full platform vs. LiteLLM alone.

**What the AI Control Plane adds on top of LiteLLM:**
- Admin UI with full CRUD for models, budgets, teams, and keys
- Agent Gateway with MCP protocol support
- Semantic caching (embedding similarity, not just Redis exact match)
- Cedar policy engine for routing decisions
- LangGraph workflow templates with Temporal orchestration
- A2A Runtime for agent-to-agent communication
- Pre-built Grafana dashboards (platform overview + FinOps)
- Budget webhook with soft/hard limit enforcement
- Cost predictor with per-request estimates
- FinOps reporter with CSV/JSON export
- Deploy-to-gateway flow for MCP config sync
- Production-ready Kubernetes manifests with Terraform

**Best for:** LiteLLM standalone if you just need a simple LLM proxy. AI Control Plane if you need the full enterprise platform.

### vs. Helicone

Helicone focuses on LLM observability, logging, and analytics.

**Where Helicone is stronger:**
- Deep request/response logging with search
- Prompt experimentation and evaluation
- User analytics and session tracking

**Where AI Control Plane is stronger:**
- Active proxy (not just logging) -- routing, failover, caching
- Budget enforcement blocks over-budget requests
- MCP tool integration and workflows
- Self-hosted with no data leaving your infrastructure
- Cedar policy engine

**Best for:** Helicone if you primarily need LLM observability. AI Control Plane if you need an active gateway with cost control.

## When to Choose the AI Control Plane

The AI Control Plane is the best fit when you need:

- **Multi-provider resilience** -- automatic failover across OpenAI, Anthropic, Google, and others
- **Cost governance** -- per-team budgets with enforcement, not just visibility
- **Self-hosted control** -- data stays in your infrastructure (no cloud dependency)
- **AI-native features** -- semantic caching, MCP tools, workflow orchestration
- **Operational maturity** -- Grafana dashboards, OTEL tracing, Prometheus metrics out of the box
- **Agent infrastructure** -- MCP + A2A protocol support for building AI agents

## Deployment Options

| Option | Description |
|--------|-------------|
| **Docker Compose** | Local development, single-server deployments |
| **Kubernetes (Kustomize)** | Production multi-node with auto-scaling |
| **Terraform (GCP GKE)** | Infrastructure-as-code for Google Cloud |

All options include the full platform. No feature is cloud-only or locked behind a paid tier.

## Related Guides

- [Quickstart](./quickstart.md) -- get running in 5 minutes
- [API Integration](./api-integration.md) -- code examples in all languages
- [Cost Management](./cost-management.md) -- budgets and FinOps
