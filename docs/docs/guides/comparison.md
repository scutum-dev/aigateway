# Comparison with Alternatives

An honest assessment of how the AI Control Plane compares to standalone LiteLLM, standalone Agent Gateway, and other AI infrastructure platforms — including what changed when both upstream projects added features that overlap with ours.

## The Landscape Shift (2025-2026)

This platform was designed when LiteLLM was primarily an LLM proxy and Agent Gateway was an MCP-only gateway. Both have evolved significantly:

| Feature | Before LiteLLM v1.80 | After LiteLLM v1.80+ |
|---------|----------------------|----------------------|
| Admin UI | Basic, limited | Full Next.js dashboard with CRUD |
| MCP support | None | Native MCP registry + tool namespacing |
| A2A support | None | A2A gateway + Agent Hub |
| Guardrails | Third-party only | Built-in PII, toxicity, prompt injection |
| Prompt management | None | Prompt Studio with versioning |
| SSO | Enterprise only | Free for up to 5 users |

| Feature | Before Agent Gateway v0.12 | After Agent Gateway v0.12+ |
|---------|---------------------------|----------------------------|
| Admin UI | None | Built-in UI at port 15000 with CRUD |
| LLM proxy | None | Multi-provider routing + failover |
| Auth | Basic | JWT, OAuth 2.0, mTLS, API key, ExtAuthz |
| Policy engine | Basic | CEL-based authorization (5-500x faster) |
| Prompt guards | None | PII blocking, prompt injection, tool poisoning |
| Governance | Solo.io project | Linux Foundation project (AWS, Google, Microsoft, Anthropic) |

### What This Means for Us

Many features we originally built as unique differentiators are now available natively in the upstream tools. We've adapted by focusing on what neither tool provides alone: **the glue layer, workflow orchestration, and unified operations**.

---

## What We Add vs. What's Already There

### Features Only in This Platform

| Feature | Why it matters |
|---------|----------------|
| **Unified Admin UI** | One React app for LiteLLM config + Agent Gateway config + workflows + guardrails. Without this, operators use LiteLLM's UI at `:4000/ui` AND Agent Gateway's UI at `:15000` separately. |
| **DB-backed gateway config** | MCP servers and A2A agents stored in Postgres with full CRUD. Config survives file loss, is queryable, auditable, and version-trackable. Agent Gateway alone uses static YAML files. |
| **Atomic MCP + A2A deploy** | One button deploys both MCP servers and A2A agents to the gateway config simultaneously. Without this, you edit YAML manually. |
| **Workflow orchestration** | LangGraph templates (research, coding, data-analysis) backed by Temporal for durable execution. Neither LiteLLM nor Agent Gateway offers multi-step AI workflows. |
| **FinOps suite** | Cost predictor (per-request estimates), budget webhook (soft/hard limits with Slack/PagerDuty/email alerts), FinOps reporter (CSV/JSON export). Goes beyond LiteLLM's built-in spend tracking. |
| **Pre-built Grafana dashboards** | Combined LiteLLM + Agent Gateway metrics in purpose-built dashboards. |
| **Production Kubernetes** | Kustomize manifests + Terraform (GCP GKE) for the entire stack, not just individual services. |

### Features We Proxy (from LiteLLM)

These features exist in LiteLLM — our Admin API provides a unified interface to them:

- Model management (add/remove models via LiteLLM API)
- API key management (virtual keys with budgets and rate limits)
- Team/org management (hierarchical with budgets)
- Budget tracking (per-key/team/user spend)
- Guardrail configuration

### Features We Don't Duplicate

These work natively in the upstream tools — we don't reimplement them:

- **LiteLLM**: Prompt Studio, SSO, batch API, traffic mirroring, pass-through endpoints, 20+ logging integrations
- **Agent Gateway**: MCP federation, A2A protocol routing, CEL authorization, OAuth 2.0, mTLS, tool poisoning protection, xDS dynamic config, Kubernetes Gateway API CRDs

---

## Competitor Comparison (Updated February 2026)

| Feature | AI Control Plane | LiteLLM Standalone | Agent Gateway Standalone | Portkey | Kong AI Gateway | Helicone |
|---------|-----------------|-------------------|-------------------------|---------|-----------------|----------|
| **LLM proxy** | Via LiteLLM (100+ models) | Native (100+ models) | Native (multi-provider) | 250+ models | Via plugins | Proxy only |
| **MCP support** | DB-backed CRUD + deploy | Native registry | Native federation | MCP Gateway | MCP Registry | No |
| **A2A support** | DB-backed CRUD + deploy | Native A2A gateway | Native A2A protocol | No | No | No |
| **Workflow orchestration** | LangGraph + Temporal | No | No | No | No | No |
| **Unified admin UI** | Yes (one UI for both systems) | Own UI only | Own UI only | Own dashboard | Konnect console | Dashboard |
| **DB-backed config** | Postgres (MCP + A2A) | Postgres (keys/teams) | Static YAML/xDS | Cloud-managed | Kong DB | Cloud-managed |
| **Atomic deploy** | MCP + A2A together | N/A | Manual config | N/A | N/A | N/A |
| **FinOps suite** | Predictor + webhook + reporter | Built-in spend tracking | No | Real-time tracking | Token rate limiting | Zero-markup billing |
| **Cost governance** | Soft + hard limits, per-team | Per-key/team limits | No | Alerts | Enterprise only | No |
| **Grafana dashboards** | Pre-built (LiteLLM + gateway) | No (Prometheus only) | No (Prometheus only) | Built-in charts | Custom | Built-in charts |
| **Self-hosted** | Yes (Docker/K8s) | Yes | Yes | Cloud + self-host | Yes | Cloud + self-host |
| **Open source** | Yes (MIT) | Yes (MIT) | Yes (Apache 2.0) | Gateway OSS, platform SaaS | Core OSS, enterprise paid | Apache 2.0 |
| **Pricing** | Free | Free + $250/mo enterprise | Free | $49-499/mo + enterprise | $50K+/yr enterprise | Free + usage-based |

### vs. LiteLLM Standalone

LiteLLM v1.80+ is a comprehensive platform on its own. The honest comparison:

**Where LiteLLM standalone is stronger:**
- Prompt Studio with versioning (we don't have this)
- SSO (free for up to 5 users)
- 20+ logging integrations (Langfuse, DataDog, W&B, etc.)
- Batch API, traffic mirroring, pass-through endpoints
- Native MCP registry with permission management per key/team/org
- Native A2A Agent Hub
- Larger community and faster release cadence

**Where this platform is stronger:**
- Workflow orchestration (LangGraph + Temporal) — LiteLLM has no equivalent
- DB-backed Agent Gateway config (MCP servers + A2A agents in Postgres, not YAML files)
- Atomic gateway deploy (MCP + A2A pushed together)
- FinOps suite (predictor, budget webhook with soft/hard limits, CSV/JSON export)
- Pre-built Grafana dashboards combining LLM + agent metrics
- Production Kubernetes manifests for the full stack (LiteLLM + Agent Gateway + observability)

**Best for:** LiteLLM standalone if you don't need Agent Gateway, workflows, or advanced FinOps. This platform if you run both LiteLLM and Agent Gateway and want unified operations.

### vs. Agent Gateway Standalone

Agent Gateway v0.12+ is a capable standalone product with its own admin UI.

**Where Agent Gateway standalone is stronger:**
- Built-in LLM proxy with multi-provider failover
- CEL-based authorization (5-500x faster than Cedar in v0.12)
- OAuth 2.0, mTLS, ExtAuthz — enterprise-grade auth
- Tool poisoning protection
- OpenAPI-to-MCP bridge (turn REST APIs into MCP tools)
- xDS dynamic configuration for Kubernetes
- Kubernetes Gateway API CRDs
- Linux Foundation governance (AWS, Google, Microsoft, Anthropic backing)

**Where this platform is stronger:**
- DB-backed config management (Postgres instead of static YAML)
- Unified UI for LLM operations + agent config
- LiteLLM integration for cost tracking and budget enforcement
- Workflow orchestration
- FinOps reporting and alerting

**Best for:** Agent Gateway standalone if you only need MCP/A2A/LLM proxying. This platform if you also need LiteLLM's cost governance and workflow orchestration.

### vs. Portkey

**Where Portkey is stronger:**
- 250+ model support, polished cloud-hosted option
- 50+ built-in guardrails
- MCP Gateway with Lasso Security partnership
- Prompt management and A/B testing
- Enterprise SSO and compliance

**Where this platform is stronger:**
- Fully self-hosted (no data leaves your infrastructure)
- Workflow orchestration (LangGraph + Temporal)
- No per-request pricing
- Agent Gateway integration for MCP/A2A protocols
- DB-backed gateway config management

### vs. Kong AI Gateway

**Where Kong is stronger:**
- Battle-tested enterprise API gateway (100+ plugins)
- MCP Registry in Konnect
- Enterprise support and SLAs

**Where this platform is stronger:**
- Purpose-built for AI (not a general API gateway with AI plugins)
- Workflow orchestration
- LiteLLM integration (100+ models pre-configured)
- No $50K+/year enterprise license required

### vs. Azure APIM / AWS Bedrock

**Where cloud providers are stronger:**
- Azure APIM: Only platform with both MCP (GA) and A2A (preview) governance
- AWS Bedrock AgentCore: Fully managed MCP gateway with zero-code tool creation
- Deep IAM integration, compliance certifications

**Where this platform is stronger:**
- Multi-cloud / cloud-agnostic (not locked to one provider)
- Self-hosted (data stays in your infrastructure)
- Workflow orchestration
- No cloud vendor lock-in
- Free

---

## Roadmap Differentiators

Features we're building that none of the alternatives currently offer:

### Cross-System Policy Enforcement
Cedar policies applied uniformly across LLM requests (LiteLLM) + MCP tool calls + A2A agent invocations. Today, LiteLLM has its own auth and Agent Gateway has CEL — nobody enforces policies across both systems.

### Unified Audit Trail
Who deployed what config, when, to which gateway, with what policy. Full change history for MCP servers, A2A agents, and LLM configurations in a single queryable database.

### Workflow Marketplace
Sharable workflow templates beyond the 3 built-in ones. Organizations can publish and discover workflow patterns (RAG pipelines, evaluation suites, data processing chains).

### Multi-Tenant SaaS Mode
Host the platform for multiple organizations with isolated databases, budgets, and gateway configs. Neither LiteLLM nor Agent Gateway offers this as a turnkey solution.

### Cost Attribution Across Agents
Track costs not just per LLM request, but per workflow execution, per A2A agent invocation, per MCP tool call — unified in one FinOps view.

### Config Drift Detection
Compare the deployed gateway config against the database state. Alert when someone manually edits the YAML file, breaking the DB-as-source-of-truth guarantee.

---

## When to Choose This Platform

Choose this platform when you need:

- **Both LiteLLM and Agent Gateway** — and want one UI, one DB, one deploy for both
- **Workflow orchestration** — multi-step AI workflows with durable execution
- **FinOps governance** — beyond basic spend tracking (soft/hard limits, alerts, CSV export)
- **Self-hosted control** — no cloud dependency, data stays in your infrastructure
- **Production Kubernetes** — full stack deployment with Terraform

Choose something else when:

- **You only need an LLM proxy** — LiteLLM standalone is sufficient
- **You only need MCP/A2A routing** — Agent Gateway standalone is sufficient
- **You want a managed cloud service** — Portkey, AWS Bedrock, or Azure APIM
- **You want best-in-class observability** — Helicone or Braintrust
- **You need enterprise API management** — Kong AI Gateway

---

## Related Guides

- [LiteLLM Deep Dive](./litellm-integration.md) — what we use, what we don't
- [Agent Gateway Deep Dive](./agentgateway-integration.md) — integration details
- [Cost Management](./cost-management.md) — budgets and FinOps
- [Quickstart](./quickstart.md) — get running in 5 minutes
