---
title: Risk-Bounded Autonomous Remediation
hide:
  - navigation
---

# Risk-Bounded Autonomous Remediation

**Engineering whitepaper · Scutum · 2026**

!!! note "What this is"
    A design note describing how Scutum's SRE agent decides whether an LLM-proposed remediation should auto-execute or require operator approval. It is **not** peer-reviewed research — there are no empirical results here. The math is standard multi-objective scoring; the contribution is the decomposition we settled on after operator interviews. Empirical results, when we run them, publish separately as research.

## Why this exists

A modern AI infrastructure deployment surfaces incidents through several channels: provider-side error rate spikes, latency-percentile excursions, budget breaches, SLA violations, guardrail strikes. Each is observable from instrumentation we already collect (OpenTelemetry traces, Prometheus metrics, the application's own audit log).

Until recently, remediation was the operator's job. The operator: (a) interprets the signal, (b) hypothesises a cause, (c) selects a corrective action from a small mental allow-list (re-route, circuit-break, raise a limit, call a colleague), (d) executes it.

LLMs can do (a)–(c) in seconds. They cannot, today, be trusted to do (d) without bound — both because the model occasionally hallucinates plausible-but-wrong remediations and because the action space contains operations whose blast radius we'd never want a non-human to choose unilaterally (dropping a budget cap, disabling an SSO provider, shutting down a region).

The question we formalise is: **given an action proposed by an LLM agent against the current platform state, what threshold of confidence-and-safety is sufficient to bypass operator approval, and how do we compute it cheaply enough to run at every action?**

## The action library

Let \(\mathcal{A}\) denote the *constrained* action library the agent may propose from. We treat \(\mathcal{A}\) as a closed set, written by humans, every entry of which has:

- A **type** \(\theta(a) \in \Theta\) — for example: `route.circuit_break`, `route.fallback_swap`, `limit.raise`, `alert.page_oncall`, `guardrail.disable`.
- A **parameter schema** — a typed JSON schema constraining the arguments. The agent fills it; the schema validates.
- A **dry-run** that simulates the action against the current state without effecting it; this is the source of the state-validity score below.
- An **inverse** \(a^{-1}\), where one exists. The agent may not propose actions without inverses.

Closing \(\mathcal{A}\) under these constraints rules out an enormous class of incidents-by-LLM. The agent cannot construct an action; it can only fill in a template.

## The risk score

We define

\[
R(a, s) = \min\Bigl( 100,\ \max\bigl( w_{B}\, B(a, s) + w_{R}\, \mathrm{Inv}(a, s) + w_{V}\, V(a, s) + w_{P}\, P(a, s),\ 0 \bigr) \Bigr)
\]

with weights \(w_B, w_R, w_V, w_P \ge 0\) summing to 100 (so the score lives natively in \([0, 100]\)). The four components:

### Blast radius \(B(a, s)\)

Blast radius captures *how many entities the action affects*. Concretely, for an action targeting a set \(\mathcal{E}_a \subseteq \mathcal{E}_s\) (where \(\mathcal{E}_s\) is the set of teams, models, or providers active in state \(s\)):

\[
B(a, s) = 100 \cdot \min\!\left( 1,\ \frac{|\mathcal{E}_a|}{|\mathcal{E}_s|} \right)
\]

Re-routing a single team's traffic = small \(B\); disabling a provider for the whole organisation = large \(B\). The function is monotone in the affected fraction, capped at 100.

A worth-discussing variant uses a *concave* mapping (e.g. \(B \propto \log |\mathcal{E}_a|\)) — punishing the first affected team less than the linear form, because operators tolerate small surgical actions more readily than the math suggests. We have not, in v0.1, observed evidence that the linear form mis-calibrates against operator preferences.

### Reversibility \(\mathrm{Inv}(a, s)\)

Some actions are perfectly reversible (a 5-minute circuit-breaker that auto-restores). Some are technically reversible but operationally costly (raising a budget cap creates an audit row that's hard to redact). Some are not reversible at all (paging on-call — you can't un-page).

We score reversibility on a four-step ordinal scale (auto-reverting → trivially reversible → audit-trail-only → irreversible). Each bucket maps to a fixed point in \([0, 100]\), with auto-reverting at 0 and irreversible at 100; the intermediate values are operator-tunable.

The discreteness is intentional. Operators reason about reversibility categorically, not continuously. Forcing the agent into one of four buckets is auditable and prevents weights from being tuned around fractional differences that don't exist in practice.

### State validity \(V(a, s)\)

Even a low-blast, reversible action can be wrong if it's predicated on a misread of the current state. \(V\) measures *how much of the agent's reasoning about \(s\) is currently true*.

Concretely, every proposed action carries a list of *preconditions* \(\mathcal{P}_a\) — facts the agent claims about \(s\) that must hold for the action to be safe. The dry-run evaluates each precondition against live state and returns a list of failures \(\mathcal{F}_{a,s} \subseteq \mathcal{P}_a\):

\[
V(a, s) = 100 \cdot \frac{|\mathcal{F}_{a,s}|}{|\mathcal{P}_a|}
\]

If every precondition holds, \(V = 0\) (safe). If half are stale, \(V = 50\). If the agent's mental model has fully diverged from reality, \(V = 100\) and the action is gated by the threshold alone.

This is the component most analogous to a model-checking gate. It's also where most of v0.1's per-action latency goes — the dry-run runs the full preconditions list against postgres + the LiteLLM SpendLogs view.

### Operational pressure \(P(a, s)\)

Two actions can have identical blast / reversibility / validity profiles but feel very different at 3am on a Friday vs 2pm on a Tuesday. Operational pressure encodes contextual modifiers as a sum of indicator functions:

\[
P(a, s) = \sum_{i} \mathbb{1}\!\bigl[\phi_i(s)\bigr] \cdot \delta_i
\]

where the \(\phi_i\) read runtime context (after-hours window per timezone, the platform's change-freeze calendar set in the Admin Console, a cascading-incident detector that fires when several related incidents are open simultaneously), and the \(\delta_i\) are operator-tunable nudge magnitudes. \(P\) is bounded above by a per-deployment cap.

The intent is to make the same action that auto-executes during business-hours green-zone get gated overnight or during a freeze. Specific \(\delta_i\) values ship as defaults; operators tune them per deployment based on their own risk posture.

## The human-in-loop gate

With \(R(a, s)\) computed, the threshold \(\tau\) is the only knob the operator turns:

\[
\text{execute}(a, s) = \begin{cases}
\textsf{auto} & R(a, s) \le \tau \\
\textsf{request\_approval}(a, s) & R(a, s) > \tau
\end{cases}
\]

Default \(\tau = 40\) in Scutum's shipping config. Operators tune it down in the early weeks (more gating = more trust-building), then up as their calibration converges.

A useful frame: \(\tau\) is the operator's *agency budget*. Setting \(\tau\) high authorises the agent to take more autonomous action; setting it low recovers human control at the cost of latency.

## Why a linear aggregation, not a learned one

We use a linear weighted sum across components. Two alternatives we considered and rejected:

**Worst-case (max).** Setting \(R = \max(B, \mathrm{Inv}, V, P)\) is conservative but causes one bad component to mask three good ones. In practice this disables auto-execution for almost every non-trivial action, defeating the purpose.

**Learned (e.g. logistic regression on operator approval data).** This is the right long-term answer. We cannot ship it in v0.1 because the dataset doesn't exist yet — the agent has to run for several weeks per deployment to generate enough labels. The linear form is the bootstrap.

The decomposition itself, though, is the more important contribution than the aggregation. Operators auditing a proposal want to ask "*why* was this scored 35?" — the linear form gives them a per-component breakdown they can inspect (Scutum's UI displays this). A learned model would make audit harder unless paired with explainability work we haven't done yet.

## How this maps to what ships

The shipping system follows §3 directly. Each action proposed by the LLM is scored on the four components, weighted-summed, and clamped to \([0, 100]\). The component weights are *empirically calibrated* — initial values from operator interviews, refined over the first weeks of each deployment against approval/reject signals. Operators who want to inspect or tune weights for their own deployment can do so from the Admin Console; we don't publish a single canonical setting because what's correct varies meaningfully by industry, on-call ratio, and regulatory posture.

The state-validity component (§3.3) is the hottest part of the inner loop. The dry-run evaluator runs each precondition against live state with a per-action time budget; preconditions that exceed the budget are reported as `unknown` and treated as failures (gate towards human approval rather than guess). The dataset of preconditions per action class is the part of \(\mathcal{A}\) we treat as proprietary, since (a) it's the hard part of the design and (b) it's directly tied to operational safety.

The breakdown the operator sees on every proposal — \(B, \mathrm{Inv}, V, P\) values plus the aggregated score — is exposed in the Admin Console's incident view. Audit-friendly by construction.

## What we don't know yet

The above is shipped. The interesting open problems:

**(Q1) Calibration drift.** Does an LLM agent trained on incidents from Q1 generalise to Q4 once the platform has evolved? We expect drift but haven't measured it. A protocol would be: replay Q1 incidents through a Q4-state-aware agent and compare proposed-action distributions.

**(Q2) Operator preference learning under sparse labels.** The agent generates 5–50 proposals/week per deployment. Most are auto-executed (no label). Approvals/rejections are sparse. Learning a per-deployment refinement to \(\tau\) or to weights \(W\) under this label sparsity is a genuine semi-supervised problem.

**(Q3) Action-space completeness.** \(\mathcal{A}\) is hand-curated. Empirically, most incidents in our test fleet are addressed by a 9-action library — but rare incidents fall outside it. When the agent has no good action, it currently escalates to "page on-call." A better answer is *agent-proposed action templates*, a pull-request-shaped workflow where the agent suggests a new action class to add to \(\mathcal{A}\) for human approval. Open whether this should sit in the SRE agent itself or a meta-agent.

**(Q4) Multi-action plans.** v0.1 scores one action at a time. A proposal to "circuit-break X *and* re-route to Y" is approximated as two independent actions with combined-risk \(\sum R_i\) — clearly wrong (the actions are entangled). Compositional risk over plans of length \(>1\) is unsolved.

**(Q5) Adversarial preconditions.** \(V\) trusts the agent to enumerate \(\mathcal{P}_a\) honestly. A misaligned (or compromised) agent could omit preconditions to force \(V = 0\). Sketch of a defence: have the agent and a separate "auditor agent" each generate preconditions; require their union to evaluate.

---

If you're running an SRE workflow and any of Q1–Q5 resonates, write to us — [hello@scutum.dev](mailto:hello@scutum.dev). We're collecting incidents data from early Scutum deployments and will publish empirical results separately as a research note when the dataset matures. The closest prior thinking is in the *safe exploration* and *human-in-the-loop RL* literatures, and we draw on those framings, but our domain (a live infrastructure platform, not a simulator) is sufficiently different that direct citation isn't useful here.
