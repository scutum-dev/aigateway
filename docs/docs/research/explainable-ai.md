---
title: Explainable AI — at the platform layer
hide:
  - navigation
---

# Explainable AI

**Scutum Research · 2026**

The XAI literature usually asks: *can we explain why this model produced this output?* That's a hard, important question, with a substantial body of work behind it — LIME (Ribeiro et al., 2016), SHAP (Lundberg & Lee, 2017), influence functions (Koh & Liang, 2017), more recent mechanistic-interpretability work (Bricken et al., 2023; Olah et al., ongoing).

Our perspective comes from being one layer up. We're not trying to explain the model's reasoning — we don't have access to the gradients, and even if we did, the production-trace explanations the field can currently produce don't operationalise into the kind of decision-support an operator needs at 3am during an incident. What we *can* do, reliably, is explain the **platform's decision** — why the request was routed where it was, why the risk score landed at 35, why the action was gated, why the cache missed.

This is a different conversation from model interpretability, and we think it's been under-explored.

## Audit-as-explanation

A model's decision is opaque. A platform's decision doesn't have to be. Every Scutum mutation writes a row to the audit log with the actor, the action, the resource, the changes (as a JSONB diff), the IP, and the timestamp. Every routing decision, every cache hit/miss, every guardrail strike is observable through OpenTelemetry traces. Every SRE agent action carries a structured reasoning chain — including the four risk-score components and what each contributed.

This isn't novel as a concept; structured-logging-as-audit is decades old. What we think is novel is the claim that **for AI infrastructure, the audit log is the operationally-useful explanation surface**. When an operator asks "why did this happen?", the answer is rarely "look at this attention head"; it's "look at this audit row, this routing decision, this guardrail evaluation, in this order." Doshi-Velez & Kim's (2017) *Towards a Rigorous Science of Interpretable Machine Learning* makes a related point about evaluation in deployed contexts — the explanation that's useful is the one that supports the operator's downstream decision, not the one that maximally describes the model.

## Decision provenance for routing and remediation

Three decisions Scutum makes per request that benefit from explicit provenance:

**Routing.** When the proxy chose `provider=anthropic, model=claude-haiku-4.5`, the operator can ask: was this choice a function of cost? latency? quality? Was the cheaper provider available but worse-quality this hour? Was a higher-quality option above the cost-elasticity bound? The scalarised utility from the [Cost-Aware Multi-Provider Routing](../whitepapers/cost-aware-routing.md) whitepaper makes this answerable as a per-request breakdown. That's an explanation in the platform's terms — not the model's.

**Remediation.** When the SRE agent proposed "circuit-break provider X for 5 minutes", the audit shows: the triggering event payload, the LLM's diagnosis, the proposed action, each of the four risk components, the threshold at the time, and the operator who approved. An operator reviewing the action a week later can reconstruct the decision exactly.

**Cache hit.** When a response came from the semantic cache, the audit row includes the cosine similarity to the cached prompt, the cache age, and the route the cache served. An operator suspicious of a stale response can ask "why did this hit?" and get a deterministic answer.

In each case, the explanation is *complete* (no hidden inputs), *deterministic* (recomputable from the audit row), and *operator-readable* (in terms of the platform's surface, not the model's).

## What infrastructure-layer XAI doesn't claim

The case for platform-layer explainability isn't a case against model-layer interpretability. They serve different operators on different timescales. When a regulator asks "was this decision biased?", the answer often *needs* to be model-layer (and is currently hard to give). When a CISO asks "was this decision authorised?", the answer is platform-layer (and we can give it cleanly).

We're also not claiming structured audit replaces the need for model-side interpretability research. If a model produces racist content, the platform telling you "the action library allowed this output to leave" is correct but unhelpful. The case for mech-interp is real; it's just orthogonal to ours.

## Open questions

**Provenance over multi-step workflows.** When an A2A workflow touches three providers and two MCP servers, can the audit be reconstructed end-to-end into a single coherent explanation? v0.1 stores per-step rows; the provenance is implicit in the timestamps. Making it explicit — the workflow as a DAG with a hash chain — is on the roadmap.

**Counterfactual platform decisions.** If the operator asks "what would the routing have been if the latency budget were 200ms instead of 500ms?", v0.1 doesn't answer. Computing counterfactual platform decisions over historical traffic is a useful affordance for tuning preferences; the implementation is non-trivial because it has to replay against the *historical* state, not current state.

**The intersection with model interpretability.** When a guardrail fires, the explanation is currently the rule that matched. A more useful explanation would be both — the rule, plus a model-side feature that fired on the same content. Crossing the platform/model boundary in explanation is hard but tractable.

## How this connects to what we ship

The Admin Console's audit page is the user-visible surface. It supports filtering by actor, action, resource, time, and free-text — and exports cleanly to CSV/JSON for downstream tools. The SRE Agent page exposes the four-component risk-score breakdown alongside the LLM's reasoning chain. The cost-tracking dashboards show the per-request routing decision with the cost / latency / quality factors in the same view.

If "explainable AI" is one of the directions your team cares about, our claim is that the platform layer is doing more of the user-facing-explanation work than the literature gives it credit for. We'd welcome both pushback and collaboration.

## References

- Ribeiro, M. T., Singh, S., & Guestrin, C. (2016). *"Why Should I Trust You?": Explaining the Predictions of Any Classifier*. KDD.
- Lundberg, S. M., & Lee, S. I. (2017). *A Unified Approach to Interpreting Model Predictions*. NeurIPS.
- Koh, P. W., & Liang, P. (2017). *Understanding Black-box Predictions via Influence Functions*. ICML.
- Doshi-Velez, F., & Kim, B. (2017). *Towards a Rigorous Science of Interpretable Machine Learning*. arXiv:1702.08608.
- Bricken, T., et al. (2023). *Towards Monosemanticity*. Anthropic.
