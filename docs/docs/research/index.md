---
title: Research
hide:
  - navigation
---

# Research

Research areas we're invested in as an AI infrastructure company. We're not a frontier-model lab — we don't train foundation models, and we don't claim to publish empirical AI research at that level. What we do bring is the **infrastructure layer's perspective** on questions the field is actively working on: what gets observed, governed, and made safe at the platform layer, between the application and the model.

These essays are our positions, with real citations to the work we draw from. Each closes with the questions an AI infrastructure company is well-placed to take on, and an invitation to collaborate.

## Areas

<div class="scutum-cards" markdown>

[<strong>AI Safety</strong><span>What safety properties can the platform layer enforce that the model layer can't reliably guarantee?</span>](ai-safety.md){.card}

[<strong>Explainable AI</strong><span>At the platform layer, explainability is audit + decision provenance — not "why the model said X" but "why the platform allowed X."</span>](explainable-ai.md){.card}

[<strong>Context Window Management</strong><span>Hybrid long-context + RAG + semantic cache. When does each pay back, and what does the platform owe each pattern?</span>](context-windows.md){.card}

[<strong>RAG Performance</strong><span>MCP-as-orchestration, reranking, retrieval evaluation — and why an AI proxy is the right place to measure end-to-end.</span>](rag-performance.md){.card}

[<strong>Multi-Agent Evaluations</strong><span>A2A protocols and the eval substrate that drops out of having audit, cost, and trace data on every step.</span>](multi-agent-evaluations.md){.card}

[<strong>Self-Learning Platform</strong><span>What if the platform's configuration learned from its own operational data — routing weights, risk-score weights, cache thresholds — under bounded drift?</span>](self-learning.md){.card}

</div>

---

For shipped engineering whitepapers describing how Scutum is built today, see [Whitepapers](../whitepapers/index.md). For a cross-cut of open problems we'd like to take on (from each whitepaper's "What we don't know yet" sections), the relevant sections are [Risk-Bounded Remediation §"What we don't know yet"](../whitepapers/risk-bounded-remediation.md#what-we-dont-know-yet) and [Cost-Aware Routing §"What we don't know yet"](../whitepapers/cost-aware-routing.md#what-we-dont-know-yet).

If you're working on any of these, write to [hello@scutum.dev](mailto:hello@scutum.dev). We collaborate where there's mutual benefit and share data from design-partner deployments under research-collaboration agreements.
