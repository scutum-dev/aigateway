---
title: Scutum Documentation
hide:
  - navigation
---

# Scutum

<div class="scutum-hero" markdown>

A self-hosted *control plane* for AI infrastructure. One OpenAI-compatible endpoint, 100+ models across 9 providers, with cost governance, audit, MCP/A2A, and policy built in.

Replace ten separate tools with one platform. Run on your own cluster, your own keys, your own data.

</div>

## Start here

<div class="scutum-cards" markdown>

[<strong>Quickstart</strong><span>Get the platform running locally in under 5 minutes.</span>](guides/quickstart.md){.card}

[<strong>API Integration</strong><span>Drop-in OpenAI-compatible endpoint. Python, TypeScript, Go, curl.</span>](guides/api-integration.md){.card}

[<strong>Comparison</strong><span>How Scutum stacks up against OpenRouter, Portkey, LangSmith, Bedrock.</span>](guides/comparison.md){.card}

[<strong>Production Readiness</strong><span>Sizing, HA patterns, security posture before you ship.</span>](production/production-readiness.md){.card}

</div>

## How it fits together

```
Your apps ──► Scutum ──► OpenAI · Anthropic · Google · xAI · DeepSeek · Bedrock · Azure · Vertex · Ollama
                │
                ├─ Cost governance      budgets, chargeback, predict-before-spend
                ├─ Audit & compliance   immutable trail, 7-year retention, exports
                ├─ Policy & guardrails  Cedar policies, DLP, prompt registry
                ├─ Routing & failover   model groups, fallback chains, A/B tests
                ├─ MCP & A2A            agent gateway with allowlists
                ├─ Observability        OpenTelemetry, Prometheus, Jaeger
                └─ Workflows            LangGraph templates, Temporal agents
```

## Sections

### Getting started
- [Quickstart](guides/quickstart.md) — local stack in 5 minutes
- [API Integration](guides/api-integration.md) — code in 4 languages
- [Comparison](guides/comparison.md) — vs. OpenRouter, Portkey, LangSmith, AWS Bedrock, Apigee

### Features
- [Model Routing](guides/model-routing.md) — fallback, groups, weighted policies
- [Guardrails](guides/guardrails.md) — DLP, regex, semantic, model-based
- [Semantic Caching](guides/semantic-caching.md) — embedding-keyed cache
- [MCP Servers](guides/mcp-servers.md) — Model Context Protocol setup
- [Workflows](guides/workflows.md) — LangGraph + Temporal agents
- [Cost Management](guides/cost-management.md) — budgets, alerts, FinOps

### Operations
- [Admin Guide](guides/admin-guide.md) — page-by-page console walkthrough
- [Licensing](operations/licensing.md) — activate, refresh, troubleshoot your license
- [Observability](guides/observability.md) — OTel, Prometheus, Jaeger, Grafana
- [Cloud Deployment](operations/cloud-deployment.md) — GKE, EKS, AKS, OCI

### Production
- [Production Readiness](production/production-readiness.md) — pre-launch checklist
- [Sizing Guide](production/sizing-guide.md) — capacity planning
- [HA Patterns](production/ha-patterns.md) — multi-AZ, multi-region

### Security & FinOps
- [Threat Model](security/threat-model.md) — STRIDE analysis
- [Secret Rotation](security/secret-rotation.md) — runbooks
- [KPI Definitions](finops/kpi-definitions.md) — cost-per-request, savings rate

---

Need a hand? Reach us at [hello@scutum.dev](mailto:hello@scutum.dev) or [book a demo](https://scutum.dev/).
