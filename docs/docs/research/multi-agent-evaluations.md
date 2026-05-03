---
title: Multi-Agent Evaluations
hide:
  - navigation
---

# Multi-Agent Evaluations

**Scutum Research · 2026**

The transition from "models" to "agents" — systems that plan, call tools, observe results, and revise — has outpaced the evaluation methodology that should ground it. AgentBench (Liu et al., 2023), GAIA (Mialon et al., 2023), and SWE-Bench (Jimenez et al., 2024) push agent benchmarking forward, but each treats an agent as a closed system: you give it a task, it produces an answer, you grade. The interesting failure modes — the ones operators see in production — happen *inside* the trajectory, between agents, across protocols.

Multi-agent systems compound the problem. When one A2A runtime delegates to another, when an MCP server's response triggers a downstream tool call, when an SRE agent proposes a remediation that depends on a budget agent's prior decision — the per-step quality of each agent and the system's emergent behaviour are different things, and current benchmarks measure neither well.

This essay is about the eval substrate that drops out of having an AI infrastructure layer between the agents and the world.

## What the platform sees that the agent doesn't

In a single-agent benchmark, the eval has access to the prompt, the response, and the ground truth. In a multi-agent system, the eval needs more:

- **Inter-agent message structure.** Which agent called which, with what arguments, and what was returned.
- **Tool-call decisions.** Did the agent invoke retrieval? Did it skip a verification step it should have run?
- **Cost and latency per step.** A correct multi-agent solution that costs $50 in tokens or takes 4 minutes is operationally a failure even if the answer is right.
- **Cross-agent state.** When agent A told agent B about resource X, did B respect the constraint? Did the system as a whole stay coherent?

The platform — proxy, audit log, cost predictor, agent gateway — collects all of this by default. It's the natural eval substrate for *trajectory-level* multi-agent evaluation, not just outcome-level.

## What's missing in the published methodology

Three gaps we see, each of which an infrastructure-layer team can help close.

**End-to-end cost-quality benchmarks.** AgentBench reports task success rate; it doesn't report cost-to-complete. In production, an agent that gets the right answer 95% of the time at $0.50/task is dominated by an agent that gets it 80% at $0.05/task for most operator preferences. The literature should report Pareto fronts; mostly it reports points.

**Trajectory-level error attribution.** When a multi-agent system fails, which agent was responsible? Was it the planner that picked a bad subgoal, the retriever that missed a fact, the verifier that accepted bad output? The published evals don't decompose. The audit log decomposes naturally — every step is a separate row with the full state — and an evaluation that uses this decomposition gives operators a more useful failure signal than a single end-to-end pass/fail.

**Cross-protocol robustness.** What happens when an MCP server returns malformed JSON to an agent that doesn't expect it? When an A2A handoff drops capability scoping? When a tool's API changes mid-conversation? These are the failure modes that production multi-agent systems trip over and that single-agent benchmarks don't probe. HELM (Liang et al., 2022) introduced the idea of measuring robustness as a first-class evaluation axis; multi-agent robustness is a natural extension that hasn't been formalised.

## What an infrastructure-layer eval substrate looks like

We think the next round of multi-agent evaluation work needs three properties:

1. **Per-step structured data**, not just final-answer comparison. Audit logs and traces are the right shape; the field has historically not used them because they're not available in academic settings.
2. **Cost and latency as first-class outcomes**, alongside correctness. Reporting Pareto fronts. We've argued for this in [Cost-Aware Multi-Provider Routing](../whitepapers/cost-aware-routing.md) for the proxy layer; the same argument applies one layer up.
3. **Production-traffic anchoring.** Synthetic benchmarks help, but production-traffic distributions are different in shape (heavy-tailed task complexity, common patterns repeated, rare patterns critical). Eval methodology that doesn't anchor to production distributions misses the failure modes that matter operationally.

None of these require new academic data. They require infrastructure layers that *generate the data already* to publish anonymised aggregates with operator consent. That's an unusual research-publication path; we think it's the right one for this domain.

## Open questions

**Multi-agent regret bounds under uncertainty.** Single-agent contextual bandits have well-developed regret bounds (Auer et al., 2002; Li et al., 2010). Multi-agent equivalents — where agent A's policy depends on agent B's observed actions — are less developed. Practical question: what's the *best* a multi-agent system can do, given observable per-step costs and a fixed task?

**Compositional risk measurement.** v0.1 of the SRE agent scores each action independently; coordinated multi-action plans are approximated as the sum of individual risks. The right answer almost certainly involves measuring *interaction* risk between actions (see the [Risk-Bounded Remediation](../whitepapers/risk-bounded-remediation.md#what-we-dont-know-yet) whitepaper's open problem on this). We have not formalised it.

**Eval-driven agent design.** If we can measure per-step quality cheaply at the proxy layer, can we train an agent that *uses* the eval signal during operation — not just for offline improvement? This is the contextual-bandit framing applied to agent action selection, with the regret bound expressed in operator-relevant currency (cost, latency, audit-log noise).

**Cross-deployment benchmarks.** Single-deployment data lets us measure that *deployment*. Cross-deployment benchmarks (anonymised, aggregated) would let us measure how production multi-agent systems differ across customers, industries, and use cases. This requires cooperation across operators that AI infrastructure providers are well-placed to coordinate.

## How this connects to what we ship

The A2A runtime and workflow engine produce structured per-step trace data via OpenTelemetry. The audit log captures every administrative action and every event handler invocation. The cost predictor scores every step against per-team budgets. The Admin Console's Events page shows the full event-handler chain for any incident.

What we ship today is sufficient infrastructure for *single-deployment* multi-agent eval. What we'd like to ship next is the *cross-deployment* substrate — anonymised benchmark aggregates across consenting design-partner deployments. That's where production-grounded multi-agent evaluation work lives.

If you're working on agent evaluation methodology — particularly trajectory-level decomposition or cost-aware Pareto-front evaluation — write to us. We have data and would welcome the methodology rigour.

## References

- Liu, X., et al. (2023). *AgentBench: Evaluating LLMs as Agents*. arXiv:2308.03688.
- Mialon, G., et al. (2023). *GAIA: A Benchmark for General AI Assistants*. arXiv:2311.12983.
- Jimenez, C. E., et al. (2024). *SWE-Bench: Can Language Models Resolve Real-World GitHub Issues?* ICLR.
- Liang, P., et al. (2022). *Holistic Evaluation of Language Models (HELM)*. arXiv:2211.09110.
- Auer, P., et al. (2002). *Finite-time Analysis of the Multiarmed Bandit Problem*. Machine Learning.
