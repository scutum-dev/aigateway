# Scutum

**The unified control plane for AI infrastructure.**

Stop gluing together five AI infrastructure tools. Scutum is one control plane: LLM proxy, MCP & A2A gateway, cost governance, audit, and risk-scored SRE remediation. Drop-in OpenAI-compatible. Run it on your infrastructure, or let us run a dedicated instance for you.

- **Public site**: <https://scutum.dev/>
- **Documentation**: <https://scutum.dev/docs/>
- **Operated by**: Scuti Marketplace India (OPC) Private Limited
- **Status**: v0.1.0, open early access (May 2026)

---

## Two ways to run it

### Self-hosted

Run Scutum on your own infrastructure. One-line installer onto a Linux box, your VPC, or your Kubernetes cluster:

```sh
curl -fsSL https://scutum.dev/install.sh | sh
```

Compose-spec compatible: works with Docker, Podman, and nerdctl. No Docker Inc commercial license required. Your data, your provider keys, your audit log — all stay on your side.

Quickstart: <https://scutum.dev/docs/guides/quickstart/>

### Fully managed

Per-customer dedicated namespace in our region of choice (US East/West, EU, India, SE Asia). 24/7 on-call, automated backups, BYO KMS for your secrets. We're the processor; the platform is yours.

Compare modes: <https://scutum.dev/docs/whitepapers/managed-vs-self-hosted/>

---

## What's in v0.1.0

- **100+ models across 9 providers**: OpenAI, Anthropic, Google Vertex AI, AWS Bedrock, Azure OpenAI, xAI, DeepSeek, Mistral, and self-hosted (vLLM, Ollama, TGI).
- **OpenAI-compatible LLM endpoint** on port 4000. Drop-in replacement for direct provider calls.
- **Pre-call cost prediction** with per-team budget gates that fire **before** the request, not after.
- **Audit log on every administrative mutation**, with configurable retention up to 7 years on Enterprise.
- **Ed25519 offline license validation** — no phone-home, signature verified against bundled public key.
- **SRE agent** with four-component risk scoring (blast radius, reversibility, state validity, operational pressure) and human-in-loop approval queue.
- **MCP server registry** + Agent Gateway hot-reload for tool federation.
- **OIDC SSO** (Okta, Azure AD, Google), OpenTelemetry traces, Grafana dashboards.

What's coming next: SAML/SCIM (Q3 2026), risk-scored auto-execution (Q4 2026), per-request quality estimation for routing (Q4 2026), SOC 2 Type I (Q3 2026), Type II + HIPAA BAA (Q1 2027).

---

## Pricing — founding-customer rates

Token costs go directly to providers at list price (no markup). The fee below covers the control plane.

### Self-hosted (you run it)

- **Free Trial** — $0 for 30 days. Full features. Setup call required.
- **License** — $99/month. Unlimited team members, all providers, all models, OIDC SSO, 90-day audit log, email support.
- **License + SRE** — $179/month. Adds the SRE auto-remediation agent with HITL approval, four-component risk scoring, alerts.

### Fully managed (we run it)

- **Trial** — $0 for 30 days. Per-customer namespace, single region.
- **Business Managed** — $1,299/month. Per-customer dedicated instance, 24/7 on-call, 99.9% uptime target, BYO KMS.
- **Enterprise Managed** — from $5,000/month. Multi-region failover, 99.95% contractual SLA, BAA + custom DPA, dedicated CSM.

Founding-customer rates lock in for the first 12 months. Future tiers will be priced higher; you keep the original rate as long as you stay on the plan.

---

## Comparison

How Scutum stacks up against alternatives. Last verified 2026-05.

| Vendor | Scope | Self-host | LLM Proxy | MCP / A2A | Workflows | SRE Agent | Cost prediction | Audit |
|---|---|---|---|---|---|---|---|---|
| **Scutum** | Unified control plane | Yes | Yes | Yes | Yes | Yes (HITL) | Yes (pre-call) | Immutable |
| OpenRouter | LLM router (managed) | No | Yes | No | No | No | No | Limited |
| Portkey | LLM gateway (managed) | Enterprise | Yes | No | No | No | Partial | Yes |
| LangSmith | Observability for LangGraph | No | No | No | LangGraph only | No | No | Trace-level |
| AWS Bedrock | LLM API (single vendor) | No | N/A | No | No | No | No | CloudTrail |
| Apigee | API gateway (general) | GCP only | Generic | No | No | No | No | Yes |
| Roll your own | You build it | Trivially | You build | You build | You build | You build | You build | You build |

Found a row that's wrong? Email <hello@scutum.dev> and we'll correct it on the next deploy.

---

## Whitepapers

Engineering whitepapers describing how Scutum is built, deployed, secured, and scaled.

- **Self-Managed Best Practices** — operator playbook (day-one setup, backups, monitoring, scaling, upgrades, disaster scenarios). <https://scutum.dev/docs/whitepapers/self-managed-best-practices/>
- **Gateway Security** — threat model, trust boundaries, audit-log integrity, rotation cadences. <https://scutum.dev/docs/whitepapers/gateway-security/>
- **Managed vs Self-Hosted** — what you trade when we run it; migration paths in either direction. <https://scutum.dev/docs/whitepapers/managed-vs-self-hosted/>
- **Platform Internals** — SRE agent in production + scaling patterns + semantic cache. <https://scutum.dev/docs/whitepapers/platform-internals/>
- **Risk-Bounded Autonomous Remediation** — math behind the SRE agent's risk score. <https://scutum.dev/docs/whitepapers/risk-bounded-remediation/>
- **Cost-Aware Multi-Provider Routing** — math behind proxy routing. <https://scutum.dev/docs/whitepapers/cost-aware-routing/>

## Research

Areas an AI infrastructure company has a perspective on.

- AI Safety at the Infrastructure Layer — <https://scutum.dev/docs/research/ai-safety/>
- Explainable AI at the Platform Layer — <https://scutum.dev/docs/research/explainable-ai/>
- Context Window Management — <https://scutum.dev/docs/research/context-windows/>
- RAG Performance — measurement at the proxy layer — <https://scutum.dev/docs/research/rag-performance/>
- Multi-Agent Evaluations — <https://scutum.dev/docs/research/multi-agent-evaluations/>
- Self-Learning Platform Configuration — <https://scutum.dev/docs/research/self-learning/>

---

## Design partner program

We're working with our first five design partners. If your team has real AI infrastructure — multiple providers, governance pressure, SOC 2 ahead — and you'd rather shape the product than wait for it, this is a fit.

What design partners get: free setup, lifetime discount, weekly working sessions with the founders, your roadmap items prioritised in our shipping order.

What we ask: honesty about what's broken, permission to publish anonymised lessons (you keep your data).

→ <hello@scutum.dev>

---

## Contact

- **General**: <hello@scutum.dev>
- **Demo / sales**: <hello@scutum.dev> or book at <https://scutum.dev/>
- **Security disclosures**: <security@scutum.dev>
- **Legal / DPA / privacy**: <legal@scutum.dev>
- **Research collaboration**: <research@scutum.dev>

- **X / Twitter**: <https://x.com/scutum_dev>
- **LinkedIn**: <https://www.linkedin.com/company/scutum-dev>

---

## Legal

- Privacy: <https://scutum.dev/privacy/>
- Terms: <https://scutum.dev/terms/>
- DPA: <https://scutum.dev/dpa/>

© 2026 Scutum. Operated by Scuti Marketplace India (OPC) Private Limited.
