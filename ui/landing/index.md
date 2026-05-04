# Scutum

**The AI control plane that runs itself.**

Drop-in OpenAI-compatible proxy across 100+ models. Native MCP and A2A with Cedar policy enforcement. Pre-call cost prediction with per-team budget gates. An autonomous SRE agent that watches the stack and proposes remediations for human approval. Self-hosted by default — your data, your keys, your audit log.

- **Public site**: <https://scutum.dev/>
- **Documentation**: <https://scutum.dev/docs/>
- **Status**: v0.1.0, open early access (May 2026)

---

## Two ways to run it

### Self-hosted (default)

Run Scutum on your own infrastructure. One-line installer onto a Linux box, your VPC, or your Kubernetes cluster:

```sh
curl -fsSL https://scutum.dev/install.sh | sh
```

Compose-spec compatible: works with Docker, Podman, and nerdctl. No Docker Inc commercial license required. Data, provider keys, and audit log all stay on your side.

Quickstart: <https://scutum.dev/docs/guides/quickstart/>

### Fully managed (early access)

Per-customer dedicated namespace in a region of your choice (US East/West, EU, India, SE Asia). The platform team provisions the stack and ships the upgrades. Best-effort uptime during early access — SLA targets calibrate as production data accumulates.

Compare modes: <https://scutum.dev/docs/whitepapers/managed-vs-self-hosted/>

---

## What's in v0.1.0

- **100+ models across 9 providers**: OpenAI, Anthropic, Google Vertex AI, AWS Bedrock, Azure OpenAI, xAI, DeepSeek, Mistral, and self-hosted (vLLM, Ollama, TGI). Catalog stays current with upstream — typical lag under 48 hours.
- **OpenAI-compatible LLM endpoint** on port 4000. Drop-in replacement for direct provider calls.
- **Native MCP and A2A protocol support** with Cedar policy enforcement at the gateway. Most AI gateways don't have this.
- **Pre-call cost prediction** with per-team budget gates that fire **before** the request, not after.
- **Autonomous SRE agent** with four-component risk scoring (blast radius, reversibility, state validity, operational pressure) and human-in-loop approval queue.
- **LangGraph workflows + Temporal-backed agent patterns** for long-running orchestration.
- **OpenTelemetry traces, Grafana dashboards, semantic cache, prompt registry**.
- **Audit log on every administrative mutation** with configurable retention.
- **OIDC SSO** (Okta, Azure AD, Google).
- **BYO provider keys, no token markup** — model spend goes to providers at list price.

On the roadmap, not currently shipping: SAML & SCIM, risk-bounded auto-execution, air-gapped install, per-request quality estimation for routing.

---

## Pricing — founding-customer rates

Token costs go directly to providers at list price (no markup). The fee below covers the control plane.

### Self-hosted (you run it)

- **Free Trial** — $0 for 30 days. Full features. No credit card.
- **License** — $99/month. Unlimited team members, all providers, all models, OIDC SSO, configurable audit retention, email support.
- **License + SRE** — $299/month. Adds the autonomous SRE agent with HITL approval, four-component risk scoring, alerts.

### Fully managed (early access — we run it)

- **Trial** — $0 for 30 days. Per-customer namespace, single region.
- **Starter Managed** — $499/month. Shared multi-tenant infrastructure, single region, best-effort uptime, BYO provider keys.
- **Business Managed** — $1,299/month. Per-customer dedicated instance, single region, best-effort uptime during early access (SLA targets calibrate as production data accumulates).

Founding-customer rates lock in for the first 12 months.

---

## Comparison

How Scutum stacks up against alternatives. Last verified 2026-05.

| Vendor | Scope | Self-host | LLM Proxy | MCP / A2A | Workflows | SRE Agent | Cost prediction | Audit | Pricing model | Open source |
|---|---|---|---|---|---|---|---|---|---|---|
| **Scutum** | Unified control plane | Yes | Yes | Yes | Yes | Yes (HITL) | Yes (pre-call) | Configurable | Flat fee | No |
| OpenRouter | LLM router (managed) | No | Yes | No | No | No | No | Limited | Per-token markup | No |
| Portkey | LLM gateway (managed) | OSS basic | Yes | Partial | No | No | Post-call | Yes | Per-recorded-log | Gateway only |
| LangSmith | Observability for LangGraph | Self-host Enterprise | No | No | LangGraph only | No | No | Trace-level | Per-trace | No |
| AWS Bedrock | LLM API (single vendor) | No | Raw API | No | Step Functions | No | No | CloudTrail | Per-token | No |
| Apigee | API gateway (general) | GCP only | Generic | No | No | No | No | Yes | Per-request | No |
| TrueFoundry | AI deployment platform | Yes | Yes | MCP only | Yes | No | Partial | Yes | Flat fee | No |
| LiteLLM | OSS LLM proxy | Yes | Yes | No | No | No | Partial | Basic | Free (self-host) | Yes |

Found a row that's wrong? Email <hello@scutum.dev>.

---

## Whitepapers

- **Self-Managed Best Practices** — operator playbook. <https://scutum.dev/docs/whitepapers/self-managed-best-practices/>
- **Gateway Security** — threat model, trust boundaries, rotation cadences. <https://scutum.dev/docs/whitepapers/gateway-security/>
- **Managed vs Self-Hosted** — what changes when we run it; migration paths in either direction. <https://scutum.dev/docs/whitepapers/managed-vs-self-hosted/>
- **Platform Internals** — SRE agent in production + scaling patterns + semantic cache. <https://scutum.dev/docs/whitepapers/platform-internals/>
- **Risk-Bounded Autonomous Remediation** — math behind the SRE agent's risk score. <https://scutum.dev/docs/whitepapers/risk-bounded-remediation/>
- **Cost-Aware Multi-Provider Routing** — math behind proxy routing. <https://scutum.dev/docs/whitepapers/cost-aware-routing/>

## Research roadmap

- AI Safety at the Infrastructure Layer — <https://scutum.dev/docs/research/ai-safety/>
- Explainable AI at the Platform Layer — <https://scutum.dev/docs/research/explainable-ai/>
- Context Window Management — <https://scutum.dev/docs/research/context-windows/>
- RAG Performance — measurement at the proxy layer — <https://scutum.dev/docs/research/rag-performance/>
- Multi-Agent Evaluations — <https://scutum.dev/docs/research/multi-agent-evaluations/>
- Self-Learning Platform Configuration — <https://scutum.dev/docs/research/self-learning/>

---

## Design partner program

The first five design partners get free setup, a lifetime discount, and direct access to the team building the platform. The fit is engineering teams shipping LLM products to production who'd rather shape the platform than wait for it. Weekly working sessions; roadmap items get prioritised; logo on the page once you're ready.

→ <hello@scutum.dev>

---

## Contact

- **General**: <hello@scutum.dev>
- **Demo**: book at <https://scutum.dev/>
- **Security disclosures**: <security@scutum.dev>
- **Legal / DPA / privacy**: <legal@scutum.dev>
- **Research collaboration**: <research@scutum.dev>

- **X**: <https://x.com/scutum_dev>
- **LinkedIn**: <https://www.linkedin.com/company/scutum-dev>

---

## Legal

- Privacy: <https://scutum.dev/privacy/>
- Terms: <https://scutum.dev/terms/>
- DPA: <https://scutum.dev/dpa/>

© 2026 Scutum.
