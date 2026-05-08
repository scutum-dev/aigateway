---
title: Scutum Documentation
hide:
  - navigation
  - toc
---

<div class="scutum-hero" markdown>

# Scutum docs

The self-hosted LLM gateway. One OpenAI-compatible endpoint, 100+ models across 9 providers, with cost governance, audit, routing, and policy built in. Postgres as source of truth. Your data never leaves your infra.

</div>

<div class="scutum-cards" markdown>

[<strong>Quickstart</strong><span>Get a local Scutum stack running in under 5 minutes.</span>](guides/quickstart.md){.card}

[<strong>API integration</strong><span>Drop-in OpenAI-compatible endpoint. Python, TypeScript, Go, curl.</span>](guides/api-integration.md){.card}

[<strong>Production readiness</strong><span>Sizing, HA, security posture before you ship.</span>](production/production-readiness.md){.card}

</div>

## How it fits together

```
Your apps ──► Scutum ──► OpenAI · Anthropic · Google · Mistral · xAI · DeepSeek · Bedrock · Azure · Vertex · Ollama
                │
                ├─ Cost governance      budgets, chargeback, predict-before-spend
                ├─ Audit & compliance   immutable trail, retention policies, exports
                ├─ Policy & guardrails  Cedar policies, DLP, prompt registry
                ├─ Routing & failover   model groups, fallback chains, A/B tests
                ├─ MCP & A2A            agent gateway with allowlists
                ├─ Observability        OpenTelemetry, Prometheus, Jaeger, Grafana
                ├─ Workflows            LangGraph templates, Temporal-backed agents
                └─ SRE agent            LLM-driven incident remediation, human-in-loop
```

## What lives where

- **Getting Started** — install, point your SDK at it, see how it compares to alternatives.
- **Reference** — feature deep-dives: routing, caching, guardrails, MCP, workflows, the SRE agent, cost management, the chat product.
- **Operations** — admin console, licensing, observability, cloud deploys; production readiness, sizing, HA; security threat model + secret rotation; FinOps KPIs.
- **Reading** — whitepapers and research notes for buyers and architects who want the longer-form rationale.

---

Need a hand? Reach us at [hello@scutum.dev](mailto:hello@scutum.dev) or [book a demo](https://scutum.dev/).
