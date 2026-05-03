---
title: Whitepapers
hide:
  - navigation
---

# Whitepapers

How Scutum is built, deployed, secured, and scaled. For forward-looking work — open problems we're investigating but haven't shipped — see [Research](../research/index.md).

## Operating Scutum

<div class="scutum-cards" markdown>

[<strong>Self-Managed Best Practices</strong><span>The operator playbook: day-one setup, backups, monitoring, scaling, upgrades, disaster scenarios.</span>](self-managed-best-practices.md){.card}

[<strong>Gateway Security</strong><span>Threat model, trust boundaries, audit-log integrity, common attacks, rotation cadences. Used in customer security review.</span>](gateway-security.md){.card}

[<strong>Managed vs Self-Hosted</strong><span>What you trade when you let us run it for you, what stays yours regardless. Migration paths in either direction.</span>](managed-vs-self-hosted.md){.card}

</div>

## How the platform works

<div class="scutum-cards" markdown>

[<strong>Platform Internals</strong><span>SRE agent in production, scaling patterns past a single host, semantic cache with PII boundaries. Three meaty capabilities, one paper.</span>](platform-internals.md){.card}

</div>

## The math behind specific subsystems

<div class="scutum-cards" markdown>

[<strong>Risk-Bounded Autonomous Remediation</strong><span>How the SRE agent decides whether to auto-execute or ask for approval. Four-component risk decomposition.</span>](risk-bounded-remediation.md){.card}

[<strong>Cost-Aware Multi-Provider Routing</strong><span>Scalarised three-objective utility (cost / latency / quality) with operator-supplied weights in interpretable units.</span>](cost-aware-routing.md){.card}

</div>

---

A different way to slice the same six papers, by reader's role:

- **You're an operator considering adopting Scutum**: read [Self-Managed Best Practices](self-managed-best-practices.md), then [Managed vs Self-Hosted](managed-vs-self-hosted.md).
- **You're a security reviewer / CISO**: read [Gateway Security](gateway-security.md).
- **You're an engineer evaluating the platform's depth**: read [Platform Internals](platform-internals.md), then either of the two math papers depending on which subsystem you care about.
- **You're a researcher curious about the formal framing**: read [Risk-Bounded Autonomous Remediation](risk-bounded-remediation.md) or [Cost-Aware Multi-Provider Routing](cost-aware-routing.md). Then look at the open problems in [Research](../research/index.md).

If a paper you wanted is missing, write to [hello@scutum.dev](mailto:hello@scutum.dev). The set grows as we learn from operators.
