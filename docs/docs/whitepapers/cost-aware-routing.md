---
title: Cost-Aware Multi-Provider Routing
hide:
  - navigation
---

# Cost-Aware Multi-Provider Routing

**Engineering whitepaper · Scutum · 2026**

!!! note "What this is"
    A design note about how Scutum's proxy chooses a provider per request when cost, latency, and quality conflict. It is **not** peer-reviewed research — there are no measured results here. The math is standard multi-objective scoring; the contribution is the *framing* (operators want trade-offs in interpretable units, not load-balancing) and the operator-facing parameter shape that drops out of it.

## Why this exists

A request \(r\) arrives at the proxy. Several providers \(p \in \mathcal{P}\) can serve it. Common practice picks one based on:

- **Round-robin** (no signal used).
- **Weighted random** (an operator-set weight \(w_p\) per provider).
- **Lowest latency** (running min over recent observed latency).
- **Cheapest** (lookup of \( c_{\text{in}}, c_{\text{out}} \) from a static price table).
- **Fallback chain** (try \(p_1\); on error, \(p_2\); on error, \(p_3\)).

Each rule individually is wrong on a meaningful fraction of requests. *Cheapest* sends production traffic to a tier that fails the SLA. *Lowest latency* picks an expensive provider for a non-time-sensitive batch job. Round-robin tells the operator nothing about *why* their bill spiked.

The right question is: **what does the operator actually want optimised, and given that preference, can we compute the routing decision in a few microseconds per request?**

## Setup

Let:

- \(\mathcal{P} = \{p_1, \dots, p_n\}\) be the providers a request *can* be routed to (after policy filtering — guardrails, model-access tiers, BYO-key checks).
- \(r\) be the request; \(t_{\text{in}}(r)\) the input-token count (computed by `tiktoken` per provider's tokeniser); \(t_{\text{out}}(r)\) the *predicted* output-token count.
- \(c_p^{\text{in}}, c_p^{\text{out}} \in \mathbb{R}_{\ge 0}\) be per-provider input and output costs per token (we normalise to USD per 1M tokens internally; the math is unitless).
- \(L_p\) be the random variable for end-to-end latency on provider \(p\) (we use the empirical 1-hour-windowed sample from OpenTelemetry traces).
- \(Q_p(r) \in [0, 1]\) be the *quality score* of provider \(p\) for the type of request \(r\) — currently a per-(model-family, task-class) pair learned from operator-graded outputs and sampled benchmarks.

The cost of routing \(r\) to \(p\) is

\[
c_p(r) = c_p^{\text{in}}\, t_{\text{in}}(r) + c_p^{\text{out}}\, t_{\text{out}}(r)
\]

deterministically (modulo the prediction error in \(t_{\text{out}}\), which we discuss in §5).

## The operator's preference function

Most routing literature picks one of \(\{c, L, Q\}\) as the objective. Operators we've worked with don't think this way. They think *trade-offs*: "I'll pay $0.002 more per request if it's 25ms faster." The natural framing is a scalarised utility:

\[
U_p(r) = -\alpha\, c_p(r) - \beta\, \mathbb{E}[L_p] + \gamma\, Q_p(r)
\]

with operator-provided weights \(\alpha, \beta, \gamma \ge 0\). The provider chosen is

\[
p^*(r) = \arg\max_{p \in \mathcal{P}} U_p(r)
\]

The triple \((\alpha, \beta, \gamma)\) is the operator's preference; the units are deliberately interpretable. Setting \(\alpha = 1\), \(\beta = \gamma = 0\) recovers cheapest-routing. Setting \(\beta = 1\), others 0 recovers lowest-latency. The middle ground is where this becomes useful.

### Why scalarisation is the right framing here

A standard objection to scalarised multi-objective optimisation is that the weights are arbitrary. In our setting they're not — they have *units*:

- \(\alpha\) is "USD per request" (so \(\alpha c_p\) is in USD).
- \(\beta\) is "USD per millisecond of latency" — i.e. how much an operator will pay to save 1ms.
- \(\gamma\) is "USD per quality-score unit" — how much an operator will pay to move from a 0.7-quality model to an 0.8-quality model.

Operators *can* reason about these in concrete monetary terms. We've found in interviews that asking "how much extra would you pay per request to halve p95 latency?" gets a usable answer from most teams; the abstract weight question does not.

## The decision rule

Substituting:

\[
p^*(r) = \arg\max_{p \in \mathcal{P}} \Bigl[ -\alpha (c_p^{\text{in}} t_{\text{in}} + c_p^{\text{out}} t_{\text{out}}) - \beta\, \mathbb{E}[L_p] + \gamma\, Q_p \Bigr]
\]

This is a single-pass argmax over \(|\mathcal{P}|\) providers, evaluable in \(O(n)\) per request. Each term is either a static lookup (cost coefficients), a running statistic (mean latency, online-updated from traces), or a per-(model-family, task) hash lookup (\(Q_p\)). Total work is dominated by the tokeniser running on \(r\) — typically 50–200µs.

### Cost-elasticity bound

A more operator-friendly framing of the same rule: rather than ask for \((\alpha, \beta, \gamma)\), ask for an *elasticity bound* \(\Delta\): the maximum extra USD/request the operator will spend to gain quality. Then for any two providers \(p_i, p_j\):

\[
\text{prefer } p_i \text{ over } p_j \quad \iff \quad c_{p_i}(r) - c_{p_j}(r) \le \Delta\, \bigl( Q_{p_i}(r) - Q_{p_j}(r) \bigr)
\]

with the latency term folded into a separate budget. This formulation is exactly the dual of §4 with \(\alpha = 1\), \(\gamma = \Delta\), and a *constraint* \(\mathbb{E}[L_p] \le L^{\max}\) instead of a soft cost \(\beta \mathbb{E}[L_p]\).

Why this matters: operators interview much more confidently about \(\Delta\) ("I'll pay up to 0.5¢/request for clearly better answers") than about \(\gamma\) in absolute units.

## The output-token prediction problem

The above assumes \(t_{\text{out}}(r)\) is known. It isn't — that's what the LLM produces. We need to predict it before the call.

Scutum's cost predictor uses a *verbosity profile* per (model, task-class):

\[
\widehat{t_{\text{out}}}(r) = \min\!\Bigl( T_{\max}(r),\ \mu_{m, k}(r) + \kappa\, \sigma_{m, k}(r) \Bigr)
\]

where:

- \(\mu_{m, k}\) is the mean output-token count for model \(m\), task-class \(k\), measured from the past 30 days of `LiteLLM_SpendLogs`.
- \(\sigma_{m, k}\) is the std-dev under the same conditioning.
- \(T_{\max}(r)\) is the user-supplied `max_tokens` (a hard upper bound).
- \(\kappa\) is an operator-tunable risk parameter (default \(\kappa = 1\), giving the predictor a ~84th-percentile estimate — biased toward over-prediction so budget gates fire on the conservative side).

Empirically — across the providers we test against — this estimator carries non-trivial error, particularly for non-chat tasks where verbosity correlates poorly with input length. Worth more work; see §7.

### Why over-predict?

A budget-gate that under-predicts cost causes a failure mode operators dislike most: a request slips through the gate, the LLM produces a long completion, the team's budget is breached, alerting fires. Operators dislike *predictable* over-prediction less than *occasional* under-prediction by the same expected error magnitude. \(\kappa \ge 1\) leans the estimator into the safer regime. We've seen no operator preference for \(\kappa < 1\) in interviews to date.

## Quality \(Q_p(r)\) — the hard part

Cost is a static lookup. Latency is a running average. **Quality is the open problem.**

We currently approximate \(Q_p(r)\) as a per-(provider-model, task-class) lookup, with task-class derived from a small classifier on the request. The lookup is bootstrapped from operator grades on a sampled subset of traffic plus public benchmarks (LMArena, HELM) when no operator data exists. Concretely:

\[
Q_p(r) \approx \frac{n_{p, k}^{\text{up}} + \alpha_0\, b_{p, k}}{n_{p, k}^{\text{tot}} + \alpha_0}
\]

a Bayesian-smoothed thumbs-up rate where \(n_{p, k}^{\text{up}}\) is operator up-votes, \(n_{p, k}^{\text{tot}}\) is total graded calls, \(b_{p, k}\) is the public-benchmark prior, and \(\alpha_0\) is an operator-tunable pseudo-count that controls how quickly the score moves away from the public-benchmark prior as operator-graded data accumulates.

This is the v0.1 form. It's a deeply unsatisfying approximation — quality is task-, prompt-, and even *user-specific* in ways the per-task-class smoothing washes out. But it's an honest baseline against which to measure improvements. Anything more ambitious here is downstream of §7-Q1.

## What we don't know yet

**(Q1) Per-request quality estimation.** \(Q_p(r)\) varies dramatically *within* a task class. Predicting which provider will best handle a specific request — without running it through several providers and grading — is the high-value open problem. Candidate approaches: (a) lightweight proxy classifier trained on (request-embedding, winning-provider) pairs, (b) cross-provider distillation as a regulariser, (c) ensemble routing with budget-aware fallbacks. We have an open prototype on (a) and preliminary numbers suggest meaningful upside over the per-task-class baseline. Not yet shipped.

**(Q2) Output-token prediction beyond MAPE 20%.** The verbosity profile in §5 is a moment estimate. Tighter regions are achievable with sequence-level models (predict the *distribution* of output lengths, not the mean), but those models cost real compute per-request — the gain has to outweigh the prediction-time cost. Open. Worth measuring before designing.

**(Q3) Online preference elicitation.** Asking operators for \((\alpha, \beta, \gamma)\) once at config-time is fragile — preferences drift with traffic patterns, business pressures, and time of year. A *rolling* elicitation — periodically present the operator two side-by-side outputs at different cost/quality points and ask which they prefer — would give the system a continuously refined preference. Closest analogue is RLHF, but at the operator-config layer rather than the model-training layer.

**(Q4) Latency variance, not just mean.** §3 uses \(\mathbb{E}[L_p]\). What an operator really cares about is p95 or p99 (since SLA targets are tail-defined). Replacing the mean with a tail statistic is mathematically straightforward but breaks the convex-utility framing — argmax becomes harder to interpret. Open: is there a closed-form rule under \(L_p \sim \text{LogNormal}\) (which our trace data fits reasonably well)?

**(Q5) Multi-step plans (with caching).** Some requests are best answered by a *cascade*: first ask a cheap model; if confidence below threshold, escalate to a more expensive model. Routing with caching is a sequential decision problem — the second call's optimal provider depends on the first call's output. v0.1 doesn't handle this; users either always-cascade or never-cascade. Right framing is contextual bandits with cascade actions; we haven't formalised it.

## How this maps to what ships

The shipping system follows §3–4 directly: per request, the proxy tokenises the input, looks up the static cost coefficients and the rolling latency / quality estimates, and runs a constant-time argmax over the small set of providers that pass policy filtering. The total work is dominated by the tokeniser; the routing decision itself is a single linear scan.

The routing-decision overhead is small relative to the provider call's own latency. Users don't observe it. The interesting engineering is upstream: keeping \(\mathbb{E}[L_p]\), \(Q_p(r)\), and the verbosity profile up-to-date as traffic and provider behaviour drift — and the operator-facing surface that lets a team set their preferences in the units they actually reason about.

---

The contribution here is *framing*. The math is straightforward. The framing — *operators want trade-offs in interpretable units* — does real work in two places: it makes the routing engine explicable to people who have to defend it to finance and security, and it makes the preference parameters something an operator can reason about over time.

If you're working on any of the open problems above, write to us — [hello@scutum.dev](mailto:hello@scutum.dev). The closest prior thinking is in the contextual-bandit and multi-objective-decision-making literatures, particularly for online provider selection where \(Q_p(r)\) must be inferred from feedback rather than observed directly.
