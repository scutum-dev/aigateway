---
title: Self-Learning Platform Configuration
hide:
  - navigation
---

# Self-Learning Platform Configuration

**Scutum Research · 2026**

The platform's configuration today is a static surface that operators tune by hand: routing weights, cache thresholds, risk-score parameters, guardrail rules, budget tiers. Operators set them once at install, revisit them when something breaks, and otherwise leave them alone. That is good engineering practice — predictable behaviour matters more than marginal optimisation — but it's a missed opportunity. Every parameter the operator hand-tunes has a *correct* value that varies with the deployment's traffic, team structure, regulatory posture, and time of year. The platform has the data to learn these values continuously. It does not, currently, do so.

This essay is the case for **self-learning at the infrastructure layer**: the platform observing its own operational data and continuously refining the parameters operators would otherwise have to retune by hand. It's also a description of the failure modes this introduces — predictability, audit, drift detection — and our thinking on how to address them.

## What's tunable, and what data the platform has on it

Six parameter classes are candidates for online refinement. For each, we describe the data the platform already collects.

| Parameter | Today | Data the platform has |
|---|---|---|
| Routing utility weights \((\alpha, \beta, \gamma)\) | Operator-set at config-time | Per-request cost, latency, quality grades from operator feedback |
| SRE agent risk-score weights \((W_B, W_R, W_V, W_P)\) | Empirical defaults; operator-tunable | Approve/reject signals on every gated proposal |
| Risk-score threshold \(\tau\) | Operator-set, default 40 | Same; threshold controls the partitioning of the proposal stream |
| Semantic-cache cosine threshold | Operator-set per route, default 0.97 | Hit/miss labels, downstream user feedback |
| Verbosity-profile parameter \(\kappa\) | Operator-set, default 1 | Predicted vs actual output tokens per request |
| Guardrail rule confidence thresholds | Operator-set | Strike outcomes (true positive vs false positive, from operator review) |

Each parameter has a per-deployment *correct* value. The data needed to estimate it exists. The infrastructure to fit it does not yet ship.

## The self-learning SRE agent — concrete shape

The SRE agent is the most direct case. The risk-bounded remediation whitepaper covers the four-component decomposition; the open question (Q2 in that paper's roadmap) is whether weights can be learned per-deployment from sparse approval signals.

A concrete protocol:

1. **Maintain a posterior over each weight** under a Gaussian-process prior. Update on every approval/rejection signal using Thompson sampling.
2. **Constrain updates** so the weights stay in operator-set bounds (e.g., \(W_B \in [0.2, 0.5]\)) and don't drift below safety floors. Anything outside the bound is gated for operator approval explicitly.
3. **Detect approval-rate drift**. If the agent's recent auto-approval rate has moved outside an operator-set window — say, was 60% last month, is now 90% — surface a banner asking whether the threshold has drifted away from operator intent.
4. **Periodically retrain the action-class quality model** that drives state-validity scoring. Each action's preconditions can be learned from observed precondition-failure-then-rollback patterns.
5. **Audit every weight update** as a first-class entry in the audit log, with the data that drove it. Operators can roll back a weight update the same way they roll back a configuration change.

The literature on this is in two places: contextual bandits with sparse feedback (Li et al., 2010, *A Contextual-Bandit Approach*), and online preference learning under human-feedback bandwidth constraints (Christiano et al., 2017, *Deep RL from Human Preferences*). Neither directly fits — bandits assume independent samples; ours are correlated by deployment state. RLHF assumes the operator can express preferences over many candidates; ours produces sparse approve/reject signals on individually-presented actions.

## The self-learning platform — broader shape

Beyond the SRE agent, the same pattern applies to the proxy's routing and the cache's thresholds:

**Routing weights.** Every request the proxy serves carries observable cost and latency. Quality is observable indirectly through user feedback (thumbs-up/down) and through downstream task success. Given an operator-supplied initial \((\alpha, \beta, \gamma)\), the platform can refine the weights to minimise an operator-revealed loss function over recent traffic. The operator stays in control by setting *bounds* — "don't drop quality below 0.7" — rather than fixed values.

**Cache thresholds.** Cosine threshold is currently a per-route operator setting. A self-learning version would adjust per-route based on observed hit-quality (hits where the cached response was downvoted lower the threshold; hits with downvotes near zero raise it). The operator sets a maximum acceptable false-positive rate and the platform fits to it.

**Verbosity profile** \(\kappa\). The operator sets how risk-averse the cost predictor should be (default \(\kappa = 1\), pushing toward over-prediction). A self-learning version observes prediction error on real traffic and adjusts \(\kappa\) per (model, task-class) to match the operator's tolerance for under-prediction events.

The unifying principle: **operators set bounds and preferences; the platform fits within them.** The operator-control surface stays small (a handful of bounds per parameter class), and the platform's behaviour stays auditable (every fitted update is a logged event with its driving data).

## What this introduces — three failure modes to defend against

**Predictability erosion.** A platform whose parameters drift continuously is harder to reason about than a static one. An on-call engineer who learned the system last week can't trust their mental model this week. The defence is *bounded drift*: changes are small, are visible in the audit log, and are gated on a "stability budget" the operator owns.

**Calibration drift in operator preferences.** If the operator's preferences themselves shift but the platform learned to fit the old preferences, the platform is now wrong. The defence is *periodic preference re-elicitation*: a low-bandwidth A/B prompt every week (two sample outputs at different cost/quality points; "which would you prefer?") that re-anchors the learned weights.

**Adversarial-feedback poisoning.** A misaligned operator (or a compromised admin account) could systematically approve actions that are individually safe but collectively shift the agent's calibration toward auto-approving things the org wouldn't want. The defence is *anomaly detection on the feedback stream*: if recent approval patterns differ statistically from the deployment's history, flag for human-review.

## Open questions

**Sparse-label calibration with bounded drift.** What's the right rate of weight updates given approval volumes of 5–50 proposals/week per deployment? Too fast and weights track noise; too slow and they don't track real preferences. There's likely an information-theoretic answer here we haven't worked through.

**Cross-deployment learning with privacy.** Could one deployment's hard-won calibration help another deployment's cold-start? Federated approaches (Konečný et al., 2016) suggest yes but require careful privacy boundaries. An infrastructure provider with cross-customer perspective is well-positioned to investigate.

**Operator preference under shift.** When org-wide preferences shift (a new compliance requirement, a new exec, a budget-cut quarter), how should the learned platform adapt? Detecting the shift early matters more than tracking it perfectly.

**Self-learning vs operator agency.** A platform that learns continuously is also a platform whose operators have less direct control. The right balance — likely "operators set bounds, the platform fits within them, and the operator can override any fitted value" — is a UX question as much as a research one.

## How this connects to what we ship

We don't ship self-learning today. Every parameter mentioned above is operator-tunable but static. The SRE agent's defaults are empirically calibrated against design-partner data; the routing utility's weights are operator-set; the cache thresholds are configured per route.

The infrastructure to *enable* self-learning — audit logs of approvals, observable cost/latency/quality data, per-deployment isolation — is in place. The fitting layer is the missing piece.

If your team has thought hard about online learning under sparse feedback, calibration drift, or operator-preference elicitation in production AI systems, write to us. This is one of the directions we think infrastructure-layer research can produce empirical results faster than the academic literature, because the data is already collected — what's needed is the methodology.

## References

- Li, L., et al. (2010). *A Contextual-Bandit Approach to Personalized News Article Recommendation*. WWW.
- Christiano, P. F., et al. (2017). *Deep Reinforcement Learning from Human Preferences*. NeurIPS.
- Konečný, J., et al. (2016). *Federated Learning: Strategies for Improving Communication Efficiency*. arXiv:1610.05492.
- Russo, D., et al. (2018). *A Tutorial on Thompson Sampling*. Foundations and Trends in Machine Learning.
- Garcia, J., & Fernández, F. (2015). *A Comprehensive Survey on Safe Reinforcement Learning*. JMLR.
