# Comparison with Alternatives

An honest assessment of how the AI Control Plane compares to standalone LiteLLM, standalone Agent Gateway, and other AI infrastructure platforms.

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

Many features we originally built as unique differentiators are now available natively in the upstream tools. This document explains what remains unique, what we integrate, and where the upstream tools are stronger.

---

## What This Platform Adds

We audited every Admin API router and standalone service against what LiteLLM v1.80+ and Agent Gateway v0.12+ offer natively. The results fall into three categories: features that don't exist in either upstream tool, integration that connects the two systems, and thin proxies that add a unified auth layer.

### Unique Features (19)

These capabilities do not exist in LiteLLM or Agent Gateway.

#### Workflow & Agent Orchestration

| Feature | What it does |
|---------|-------------|
| **Workflow Engine** | LangGraph multi-step orchestration with 3 templates (research, coding, data-analysis), PostgreSQL checkpointing, WebSocket streaming, MCP tool binding, per-workflow cost tracking, pause/resume. Neither LiteLLM nor Agent Gateway has workflow orchestration. |
| **A2A Runtime** | Temporal-based durable agent orchestration with 5 workflow patterns: single, sequential, parallel, supervisor, and human-in-the-loop. Agent Gateway routes A2A messages but does not orchestrate multi-agent workflows. |

#### Enterprise Multi-Tenancy

| Feature | What it does |
|---------|-------------|
| **Organizations** | Multi-tier hierarchy: Organization > Business Unit > Team > Member with per-level roles. LiteLLM has flat teams with no org structure. |
| **Per-org SSO** | OIDC/SAML configuration scoped per organization with encrypted client secrets, group-to-org mapping, and discovery endpoint testing. LiteLLM SSO is global-only and gated to Enterprise. |

#### FinOps & Cost Governance

| Feature | What it does |
|---------|-------------|
| **Pre-request cost prediction** | tiktoken token counting with model-specific verbosity profiles and pricing tables. Predicts cost *before* the LLM call. LiteLLM only tracks cost *after*. |
| **Budget webhook** | Soft/hard budget enforcement at request time. Calls the cost predictor, blocks requests exceeding hard limits, sends alerts (Slack/PagerDuty/email) at soft limits. LiteLLM has budget limits but no pre-request prediction or multi-channel alerting. |
| **Chargeback** | Cost allocation rules (by cost center, project, department), chargeback report generation with finalization lifecycle, CSV/JSON export, and budget forecasting via weighted moving average. |
| **FinOps reporting** | Rich aggregation on top of LiteLLM's spend data: cost reports by model/user/team, trend analysis with direction detection, summary stats, and CSV/JSON export. |

#### Governance & Compliance

| Feature | What it does |
|---------|-------------|
| **SLA monitoring** | Formal SLA definitions with p50/p95/p99 latency targets, error rate and availability thresholds. Tracks violations, generates compliance reports, configures failover rules with cooldown. |
| **A/B model testing** | Create experiments with base vs. variant model, configurable traffic split, automatic metrics collection, and promote/rollback lifecycle. Integrates with LiteLLM by dynamically adding weighted model variants. |
| **Model access governance** | Three-tier access model (standard, premium, experimental) with self-service request/approve workflow, justification requirements, and auto-expiry. Syncs granted models to LiteLLM teams. |
| **Model deprecation tracking** | Track deprecation and sunset dates per model. Auto-creates LiteLLM aliases to redirect traffic from deprecated models to replacements. |
| **Admin audit trail** | Structured log of every admin action (who changed what, when) with multi-dimensional filtering and CSV/JSON export. LiteLLM logs request data but not admin configuration changes. |

#### Content Safety & DLP

| Feature | What it does |
|---------|-------------|
| **Guardrail management** | Named guardrail configurations with granular scanner toggles (prompt injection, PII, toxicity, secrets, invisible text, malicious URLs, banned topics), per-team assignment with priority, and violation event logging. LiteLLM has guardrails but they are configured in YAML, not database-driven with team-scoped assignment. |
| **DLP detectors** | Composable content detectors (regex, keyword, PII patterns) with team-scoped policies (block, redact, warn). Detector testing endpoint. Goes beyond LiteLLM's built-in scanners with user-defined rules. |

#### Developer Experience

| Feature | What it does |
|---------|-------------|
| **Prompt registry** | Versioned prompt templates with `{{variable}}` substitution, review/approval workflow (draft > pending > approved > deprecated), DLP scanning before execution, and per-version usage analytics. Richer than LiteLLM's Prompt Studio which lacks approval workflows and DLP integration. |
| **Event subscriptions** | Subscribe to platform events (budget exceeded, guardrail blocked, model error, SLA violation) via webhook, Slack, PagerDuty, email, SNS, or SQS. Filter by event type. Test event injection. Neither upstream tool has a configurable event bus. |
| **Persistent playground** | Save and load multi-model comparison sessions with public/private sharing. LiteLLM's playground does not persist sessions. |

#### Operations

| Feature | What it does |
|---------|-------------|
| **Rate limit policies** | Multi-scope policies (user, team, model, user+model, team+model, global) with RPM/TPM/RPD/TPD limits, burst multipliers, Redis-backed counter monitoring, and pre-flight check API. Syncs to LiteLLM. Extends LiteLLM's basic per-key/team limits with a composable policy framework. |

### Integration Layer (5)

These connect LiteLLM and Agent Gateway in ways neither provides alone:

| Feature | What it does |
|---------|-------------|
| **MCP server management** | DB-backed CRUD for MCP server configs in Postgres, connectivity testing, config preview, and atomic deploy to Agent Gateway's shared volume. |
| **A2A agent management** | DB-backed CRUD for A2A agent configs in Postgres, connectivity testing, deployed alongside MCP servers. |
| **Cache management** | Admin UI endpoints for viewing stats, adjusting settings, clearing entries, and browsing LiteLLM's native redis-semantic cache. |
| **Unified Admin UI** | One React dashboard for LiteLLM config + Agent Gateway config + workflows + guardrails + FinOps. Without this, operators use LiteLLM's UI at `:4000/ui` and Agent Gateway's UI at `:15000` separately. |
| **Production infrastructure** | Pre-wired OTEL Collector, Prometheus (with 28 domain-specific alert rules), 5 Grafana dashboards, Jaeger tracing, Kustomize manifests, and Terraform (GCP GKE) for the full stack. |

### Thin Proxies (4)

These forward directly to LiteLLM's API, adding only JWT authentication:

- **Model management** -- proxies to LiteLLM `/model/*`
- **API key management** -- proxies to LiteLLM `/key/*`
- **Team management** -- proxies to LiteLLM `/team/*`
- **Budget management** -- proxies to LiteLLM `/budget/*`

These exist so the Admin UI can use a single auth token for all operations rather than passing the LiteLLM master key to the browser.

### What We Don't Duplicate

These work natively in the upstream tools -- we use them as-is:

- **LiteLLM**: Prompt Studio, SSO (global), batch API, traffic mirroring, pass-through endpoints, semantic caching (redis-semantic), 20+ logging integrations (Langfuse, DataDog, W&B)
- **Agent Gateway**: MCP federation, A2A protocol routing, CEL authorization, OAuth 2.0, mTLS, tool poisoning protection, OpenAPI-to-MCP bridge, xDS dynamic config, Kubernetes Gateway API CRDs

---

## Competitor Comparison

| Feature | AI Control Plane | LiteLLM | Agent Gateway | Portkey | Kong AI | Helicone |
|---------|-----------------|---------|---------------|---------|---------|----------|
| **LLM proxy** | Via LiteLLM (85+ models) | Native (100+) | Native | 250+ | Via plugins | Proxy only |
| **MCP / A2A** | DB-backed CRUD + deploy | Native | Native | MCP only | MCP only | No |
| **Workflow orchestration** | LangGraph + Temporal | No | No | No | No | No |
| **Multi-agent orchestration** | Temporal (5 patterns) | No | No | No | No | No |
| **Multi-tenant orgs** | Org > BU > Team | Flat teams | No | No | Konnect orgs | No |
| **Per-org SSO** | OIDC/SAML per org | Global SSO | OAuth 2.0 | Enterprise | Enterprise | No |
| **Pre-request cost prediction** | Yes (tiktoken) | No (post only) | No | No | No | No |
| **Budget alerts** | Soft/hard + multi-channel | Hard limits only | No | Alerts | Enterprise | No |
| **Chargeback & allocation** | Rules + reports + export | No | No | No | No | No |
| **SLA monitoring** | Definitions + violations | No | No | No | No | No |
| **A/B model testing** | Traffic split + metrics | No | No | A/B testing | No | No |
| **Model access governance** | Tiered + approval workflow | Static assignment | No | No | No | No |
| **DLP detectors** | Custom regex/keyword/PII | Built-in scanners | Prompt guards | 50+ guardrails | No | No |
| **Prompt approval workflow** | Version + review + DLP | Prompt Studio | No | Prompt mgmt | No | No |
| **Event subscriptions** | Multi-channel bus | Webhooks | No | Alerts | No | No |
| **Admin audit trail** | Structured + export | Enterprise only | No | Enterprise | Enterprise | No |
| **Grafana dashboards** | 5 pre-built | Prometheus only | Prometheus only | Built-in | Custom | Built-in |
| **Prometheus alerts** | 28 domain rules | No | No | Built-in | Custom | No |
| **K8s + Terraform** | Full stack | Helm chart | Helm chart | Cloud | Kong Konnect | Cloud |
| **Self-hosted** | Yes (Docker/K8s) | Yes | Yes | Partial | Yes | Partial |
| **Open source** | MIT | MIT | Apache 2.0 | Partial OSS | Partial OSS | Apache 2.0 |
| **Pricing** | Free | Free + $250/mo ent. | Free | $49-499/mo | $50K+/yr | Usage-based |

### vs. LiteLLM Standalone

LiteLLM v1.80+ is a comprehensive platform on its own.

**Where LiteLLM standalone is stronger:**

- Native MCP registry with per-key/team/org permission management
- Native A2A Agent Hub
- SSO free for up to 5 users (global scope)
- 20+ logging integrations (Langfuse, DataDog, W&B, etc.)
- Batch API, traffic mirroring, pass-through endpoints
- Larger community and faster release cadence

**Where this platform is stronger:**

- Workflow orchestration (LangGraph + Temporal) and multi-agent orchestration (5 Temporal patterns) -- LiteLLM has no equivalent
- Enterprise multi-tenancy (Org > BU > Team hierarchy with per-org SSO)
- Pre-request cost prediction and budget webhook with soft/hard limits and multi-channel alerting
- Chargeback with cost allocation rules, report generation, and CSV/JSON export
- SLA monitoring with formal definitions, violation tracking, and compliance reports
- A/B model testing with traffic splitting and auto-promote/rollback
- Model access governance with tiered request/approve workflows
- Composable DLP detectors with team-scoped policies
- Prompt registry with approval workflow and DLP scanning
- Admin audit trail with structured filtering and export
- Event subscriptions across Slack, PagerDuty, email, and webhooks
- DB-backed Agent Gateway config (MCP + A2A in Postgres, not YAML)
- 5 Grafana dashboards and 28 Prometheus alert rules pre-configured

**Choose LiteLLM standalone** if you need an LLM proxy with cost tracking and don't need Agent Gateway, workflows, enterprise multi-tenancy, or advanced FinOps.

**Choose this platform** if you run both LiteLLM and Agent Gateway and need enterprise governance, workflow orchestration, FinOps, or multi-tenant operations.

### vs. Agent Gateway Standalone

Agent Gateway v0.12+ is a capable standalone product with its own admin UI.

**Where Agent Gateway standalone is stronger:**

- Built-in LLM proxy with multi-provider failover
- CEL-based authorization (5-500x faster than Cedar)
- OAuth 2.0, mTLS, ExtAuthz -- enterprise-grade auth
- Tool poisoning protection
- OpenAPI-to-MCP bridge (turn any REST API into MCP tools)
- xDS dynamic configuration for Kubernetes
- Kubernetes Gateway API CRDs
- Linux Foundation governance (AWS, Google, Microsoft, Anthropic backing)

**Where this platform is stronger:**

- DB-backed config management (Postgres instead of static YAML, survives file loss, queryable, auditable)
- Unified UI for LLM operations + agent config + workflows
- Full FinOps suite (cost prediction, budget enforcement, chargeback, SLA monitoring)
- Workflow and multi-agent orchestration
- Enterprise multi-tenancy and governance

**Choose Agent Gateway standalone** if you only need MCP/A2A/LLM proxying with strong auth.

**Choose this platform** if you also need LiteLLM's cost governance, workflow orchestration, and unified enterprise operations.

### vs. Portkey

**Where Portkey is stronger:**

- 250+ model support with polished cloud-hosted option
- 50+ built-in guardrails
- MCP Gateway with Lasso Security partnership
- Prompt management and native A/B testing
- Enterprise SSO and compliance certifications

**Where this platform is stronger:**

- Fully self-hosted (no data leaves your infrastructure)
- Workflow and multi-agent orchestration (LangGraph + Temporal)
- No per-request pricing
- Chargeback, SLA monitoring, model access governance -- enterprise FinOps features Portkey lacks
- Agent Gateway integration for MCP/A2A with DB-backed config

### vs. Kong AI Gateway

**Where Kong is stronger:**

- Battle-tested enterprise API gateway (100+ plugins)
- MCP Registry in Konnect
- Enterprise support, SLAs, and compliance certifications

**Where this platform is stronger:**

- Purpose-built for AI operations (not a general API gateway with AI plugins)
- Workflow and multi-agent orchestration
- Enterprise FinOps (chargeback, SLA monitoring, budget alerts)
- 85+ models pre-configured with fallback chains
- No $50K+/year enterprise license

### vs. Azure APIM / AWS Bedrock

**Where cloud providers are stronger:**

- Azure APIM: MCP (GA) and A2A (preview) governance with deep Azure AD integration
- AWS Bedrock AgentCore: Fully managed MCP gateway with zero-code tool creation
- Compliance certifications (SOC2, HIPAA, FedRAMP)
- Managed infrastructure with SLAs

**Where this platform is stronger:**

- Multi-cloud and cloud-agnostic (not locked to one provider)
- Self-hosted (data stays in your infrastructure)
- Workflow orchestration and multi-agent patterns
- Full FinOps suite with chargeback and SLA monitoring
- No cloud vendor lock-in, no usage-based pricing
- Free and open source

---

## Roadmap

Features we are building that none of the alternatives currently offer:

### Cross-System Policy Enforcement
Cedar policies evaluated at runtime across LLM requests (LiteLLM) + MCP tool calls + A2A agent invocations. Today, LiteLLM has its own auth and Agent Gateway has CEL -- nobody enforces policies across both systems uniformly.

### Workflow Marketplace
Sharable workflow templates beyond the 3 built-in ones. Organizations can publish and discover workflow patterns (RAG pipelines, evaluation suites, data processing chains).

### Cost Attribution Across Agents
Track costs not just per LLM request, but per workflow execution, per A2A agent invocation, per MCP tool call -- unified in one FinOps view.

### Config Drift Detection
Compare the deployed gateway config against the database state. Alert when someone manually edits the YAML file, breaking the DB-as-source-of-truth guarantee.

---

## When to Choose This Platform

**Choose this platform when you need:**

- **Both LiteLLM and Agent Gateway** -- one UI, one DB, one deploy for both
- **Workflow orchestration** -- multi-step AI workflows with durable execution
- **Multi-agent orchestration** -- Temporal-backed agent patterns (parallel, supervisor, human-in-loop)
- **Enterprise multi-tenancy** -- org hierarchy with per-org SSO
- **FinOps governance** -- pre-request cost prediction, chargeback, SLA monitoring, budget alerts
- **Governance workflows** -- model access tiers, prompt approvals, A/B testing, deprecation tracking
- **Self-hosted control** -- no cloud dependency, data stays in your infrastructure
- **Production-ready infrastructure** -- Kubernetes, Terraform, Grafana dashboards, Prometheus alerts

**Choose something else when:**

- **You only need an LLM proxy** -- LiteLLM standalone is sufficient and simpler
- **You only need MCP/A2A routing** -- Agent Gateway standalone is sufficient and faster
- **You want a managed cloud service** -- Portkey, AWS Bedrock, or Azure APIM
- **You want best-in-class observability** -- Helicone or Braintrust
- **You need enterprise API management** -- Kong AI Gateway

---

## Related Guides

- [LiteLLM Deep Dive](./litellm-integration.md) -- what we pre-configure, what we use as-is
- [Agent Gateway Deep Dive](./agentgateway-integration.md) -- integration details
- [Cost Management](./cost-management.md) -- budgets, chargeback, and FinOps
- [Quickstart](./quickstart.md) -- get running in 5 minutes
