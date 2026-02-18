# Hello World: AI Control Plane for Organizations

This guide walks through how an organization adopts the AI Control Plane — from
platform admin setup to developer usage to FinOps reporting.

## Prerequisites

```bash
# Start the platform (from repo root)
make up          # core services: LiteLLM, Admin API, Admin UI, Postgres, Redis
# or
make up-full     # everything including observability, workflows, finops
```

Verify services are running:

```bash
curl -s http://localhost:4000/health     # LiteLLM proxy
curl -s http://localhost:8086/health     # Admin API
open http://localhost:5173               # Admin UI
```

## Architecture Overview

```
Developer App (OpenAI SDK)
        │
        ▼
┌─────────────────────────────┐
│  AI Control Plane :4000     │  ← OpenAI-compatible API
│   • Cost tracking           │
│   • Rate limiting           │
│   • Model routing           │
│   • Guardrails              │
└───────────┬─────────────────┘
            │
   ┌────────┼────────┬────────────┐
   ▼        ▼        ▼            ▼
OpenAI  Anthropic  Google    Self-hosted
GPT-5   Claude    Gemini      Ollama
```

The key insight: **developers use the standard OpenAI SDK** pointing at the
AI Control Plane (`http://localhost:4000`). Zero code changes to switch
providers, add guardrails, or enforce budgets.

## Quick Start

### 1. Install dependencies

```bash
cd examples/hello-world

# Python
pip install -r python/requirements.txt

# TypeScript (optional)
cd typescript && npm install && cd ..
```

### 2. Run examples in order

| # | Script | What it shows |
|---|--------|---------------|
| 1 | `python/01_basic_chat.py` | Simplest LLM call through the control plane |
| 2 | `python/02_multi_model.py` | Same prompt → 3 providers, compare cost/speed |
| 3 | `python/03_streaming.py` | Streaming responses for real-time UX |
| 4 | `python/04_enterprise_setup.py` | Admin provisions org → teams → API keys → budgets |
| 5 | `python/05_cost_tracking.py` | Query spend by team, model, and time range |
| 6 | `python/06_guardrails_and_cache.py` | Content filtering + semantic cache |
| 7 | `typescript/basic_chat.ts` | TypeScript equivalent of example 1 |

```bash
python python/01_basic_chat.py
python python/02_multi_model.py
python python/03_streaming.py
python python/04_enterprise_setup.py
python python/05_cost_tracking.py
python python/06_guardrails_and_cache.py
```

---

## How Organizations Use This

### Platform Admin (Day 1)

The platform admin uses the Admin UI or API to:

1. **Create the organization** with a global budget cap
2. **Create teams** (Engineering, Data Science, Marketing) under the org
3. **Issue API keys** scoped to each team with per-key budgets
4. **Set guardrails** — block PII, restrict models, enforce content policies
5. **Configure rate limits** — per-team RPM/TPM caps
6. **Define model access tiers** — standard (GPT-4o-mini) vs premium (GPT-5, Claude Opus)

See: `python/04_enterprise_setup.py`

### Developer (Day 2+)

Developers get their team API key and use the **standard OpenAI SDK**:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:4000",   # ← Control Plane, not OpenAI
    api_key="sk-team-engineering-key"   # ← Team-scoped key
)

response = client.chat.completions.create(
    model="gpt-4o",                     # ← Any of 100+ models
    messages=[{"role": "user", "content": "Hello!"}]
)
```

That's it. No provider SDKs, no billing setup, no API key management.
The control plane handles routing, cost tracking, rate limiting, and guardrails.

### FinOps / Manager (Weekly)

Managers use the Admin UI dashboard or API to:

- View **spend by team** and **by model**
- Review **chargeback reports** allocated to cost centers
- Check **SLA compliance** (latency percentiles, error rates)
- Monitor **budget utilization** with forecasts
- Export reports as CSV/JSON for finance systems

See: `python/05_cost_tracking.py`

---

## What the AI Control Plane Gives You

| Without Control Plane | With AI Control Plane |
|----------------------|----------------------|
| Each team manages their own API keys | Centralized key management |
| No visibility into costs | Real-time cost tracking per team/model |
| No budget controls | Hard/soft budget limits with alerts |
| Different SDKs per provider | One SDK (OpenAI-compatible) for all |
| No audit trail | Full audit log of every config change |
| Manual model switching | A/B testing, failover, load balancing |
| No content filtering | Guardrails, DLP, prompt injection detection |
| Siloed rate limits | Granular rate limiting (user/team/model) |
