---
title: Managed vs Self-Hosted Scutum
hide:
  - navigation
---

# Managed vs Self-Hosted Scutum

**Engineering whitepaper · Scutum · 2026**

!!! note "Who this is for"
    Teams comparing the two ways to run Scutum: bring your own infrastructure, or let us run it. The platform is **the same product** in both cases — same images, same APIs, same Admin Console. The difference is who's on call, who handles capacity planning, and who absorbs the operational tax of running it well.

The decision rests on three honest questions:

1. **Do we have a platform team that wants this?** Self-hosted Scutum is well-tooled but it is real infrastructure — Postgres, Redis, multiple services, backups, monitoring, upgrades. If your team's engineers want to spend their time on this, self-host. If they'd rather spend it on your product, use managed.
2. **Are there compliance reasons we can't share infrastructure?** Some regulated environments (HIPAA, sovereign data, air-gap) require self-hosting. Most don't, especially with our SOC 2 + DPA in place. Read your DPO's actual requirements before defaulting to self-hosted.
3. **Is our usage shape predictable?** Spiky bursty traffic on managed scales transparently; on self-hosted it's a capacity-planning exercise you own. Steady predictable traffic is fine on either.

## What's in the box, both versions

These are identical regardless of who runs the platform:

- The Scutum proxy (LiteLLM-backed) on port 4000 — OpenAI-compatible, 100+ models, 9 providers, MCP/A2A
- Admin Console on port 5173 — keys, teams, budgets, audit, prompts, rate limits, model access, SLA monitor, A/B tests, events, MCP servers, A2A agents, guardrails, workflows, license, settings
- Cost predictor + budget webhook (FinOps) on tiers that include them
- SRE agent (Business and Enterprise tiers) with human-in-loop approval
- Workflow engine (LangGraph + Temporal) and A2A runtime
- The same OpenAPI surface, the same React UI, the same Postgres schema, the same audit-log shape

## What you get on managed

The managed offering is **everything in the box plus the operational work**:

| Capability | Self-managed | Managed |
|---|---|---|
| Initial install + .env config | Operator runs `curl install.sh` | We provision; you receive a console URL + service-account token |
| Backups | You write the cron + off-host job | Daily encrypted off-region backups, 14-day rolling + monthly archives |
| Monitoring + alerting | Wire to your Datadog / Splunk / etc. | We monitor; pages route to our on-call rotation first, then yours per your runbook |
| Postgres patching | You schedule maintenance windows | Zero-downtime managed-Postgres rolling upgrades |
| Scutum version upgrades | You stage + smoke-test + promote | We stage in your dedicated environment, you approve, we promote |
| Capacity scaling | You tune workers, replicas, DB tier | Auto-scales LiteLLM replicas behind the load balancer; managed Postgres tier auto-bumps |
| Security patches | You watch the changelog + upgrade | Critical CVEs land within 24h of disclosure; routine within 7 days; no operator action needed |
| Audit-log archival | You configure S3 retention | Audit data is archived to your-region object store with retention lock per your contract |
| TLS terminator + WAF | You stand up Cloudflare / nginx / NLB | Cloudflare Enterprise + WAF + Bot Mitigation included |
| 99.95% uptime SLA | You build for it | Contractual SLA with credits |
| 24/7 on-call | Your team | Our team, with escalation to your team if root-cause is in your application |
| Compliance attestations (SOC 2, ISO, HIPAA BAA) | You inherit Scutum's attestations + add your own | Same; the managed deployment is itself in our SOC 2 perimeter |

## The boundary that doesn't change

Even on managed, **your data stays in your tenancy**:

- The managed offering deploys per-customer into a dedicated namespace in our region of choice (the closest of: us-east-1, us-west-2, eu-west-1, ap-south-1, ap-southeast-1).
- Your Postgres is yours alone — not multi-tenant. Backups go to a bucket scoped to your tenancy.
- Your provider API keys live in our secrets manager, encrypted with a key you own (BYOK via AWS KMS or GCP KMS). We can call providers on your behalf; we cannot read your keys without your KMS access.
- Your audit log, prompt registry, and configuration data are isolated by tenancy and cannot be queried across customers.

The managed offering is a *managed instance*, not a multi-tenant SaaS. When we say "we run it for you", we mean: we run *your* dedicated stack on infrastructure scoped to you.

## What managed costs

Managed pricing is on the same tier ladder (Team / Business / Enterprise) as self-managed, with a managed-overhead surcharge that varies with the SLA tier. Specifics:

- **Team Managed**: ~ +50% over self-managed Team. Single region, business-hours support, 99.5% target.
- **Business Managed**: ~ +50% over self-managed Business. Single region, 24/7 support, 99.9% target.
- **Enterprise Managed**: contracted. Multi-region, 99.95% SLA with credits, BAA available, dedicated CSM.

The right way to think about the surcharge is "what's the loaded cost of one infrastructure engineer-hour in your org per month, vs what you'd spend on this." For most teams ≤ 100 engineers, managed pencils out.

## How long migrations take

Either direction is straightforward because the platform is the same artefact:

- **Self-managed → Managed**: we provision a fresh managed instance, you point your applications at the new endpoint, you backup-restore your `licenses` / `audit_logs` / config tables (we provide the script). Typical wall-clock: 2 weeks from contract signing, mostly waiting on your DNS / firewall / KMS plumbing.
- **Managed → Self-managed**: we hand you a final backup of your dedicated Postgres + your secrets-manager export. You provision your own infrastructure, restore. Typical wall-clock: 1 week (the long pole is provisioning your own Postgres + secrets manager).

There's no proprietary lock-in in either direction. The data is in standard Postgres; the configuration is in our (open) Admin API; the secrets are yours.

## When to choose which

- **Self-managed if**: you have an existing platform team, or you have a regulatory constraint that mandates it, or your org has bias toward owning all infrastructure as a strategic posture (some financial services).
- **Managed if**: you want the platform's value without buying the operational tax. This is the right answer for most teams under ~200 engineers.
- **Hybrid (rare but valid)**: managed dev/staging, self-hosted prod, or vice versa. Both sides run the same images so the testing surface is consistent.

If you're not sure, default to managed for a 30-day trial; the conversion path to self-hosted is well-trodden if you decide ops ownership matters.

## How to engage

- **Self-managed**: `curl -fsSL https://scutum.dev/install.sh | sh`. License JWT from us.
- **Managed**: write to [hello@scutum.dev](mailto:hello@scutum.dev) with your tier preference, region, and SSO setup. We'll send back a 30-minute onboarding call slot and a service-account token.

The right answer is the one that lets your team focus on what they're good at. We're happy to be the right answer either way.
