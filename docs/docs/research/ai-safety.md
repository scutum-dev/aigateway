---
title: AI Safety — the infrastructure-layer view
hide:
  - navigation
---

# AI Safety

**Scutum Research · 2026**

The frontier-model labs work on safety from the inside: how to train models that are honest, harmless, and helpful. RLHF (Christiano et al., 2017), Constitutional AI (Bai et al., 2022), and the ongoing work on weak-to-strong generalisation, reward modelling, and adversarial robustness are all forms of *baking safety into the model*.

That work is necessary. It is also, for our purposes, *insufficient*. By the time a request reaches Scutum's proxy, the model has already been trained — we have no influence on what it knows, what it refuses, or how it reasons. What we can influence is the layer around it: what the platform allows the model to do, what evidence is collected, and where the human-in-loop boundary sits.

This essay is the case for *infrastructure-layer safety* as a complementary discipline. The model researcher asks "is this model safe?" — a property of the trained artefact. The platform researcher asks "is the system around this model safe?" — a property of the deployment.

## What the platform layer can do that the model cannot

Three classes of safety properties are weak or absent at the model layer and tractable at the platform layer.

**Action-space closure.** A trained model can be asked to write SQL that drops a table. Whether it should is the model's problem; whether the resulting SQL ever executes is the platform's. By making the platform's action library a closed, hand-curated set with typed schemas — instead of letting the model construct arbitrary side-effects — we constrain the realisable harm without constraining the model's reasoning. The closure is what the SRE agent depends on for its safety profile (see the [Risk-Bounded Autonomous Remediation](../whitepapers/risk-bounded-remediation.md) whitepaper). Garcia & Fernández's *A Comprehensive Survey on Safe Reinforcement Learning* (JMLR 2015) is the canonical framing for action-space-constrained agents; we adopt the constrained-policy variant rather than the modify-the-reward variant for auditability.

**Auditable evidence.** Models forget the trajectory that led them to an output. The platform doesn't have to. Every prompt, every retrieval, every tool call, every model response can be persisted with cryptographic-grade immutability if the operator wants it. Anthropic's mechanistic interpretability work (Bricken et al., 2023; Marks et al., 2024) is one direction toward understanding *why* a model produced a given output; structured audit logging is a complementary direction that's reliable today even when the explanation isn't.

**Human-in-loop gates with bounded latency.** A model deciding whether to ask for human approval is itself an unreliable judgement. A platform deciding — based on a structured risk score whose decomposition is operator-visible — is a different shape of decision, and one that admits formal calibration. The decomposition we ship in the SRE agent (blast radius, reversibility, state validity, operational pressure) is a v0.1 of this; better decompositions are a research frontier we'd benefit from external eyes on.

## What the platform layer cannot do

Honest about the limits: nothing the platform does fixes a model that's wrong about a question of fact, or a model that complies with a policy violation when wrapped in the right prompt-injection. Models are responsible for their outputs; platforms are responsible for what's done with those outputs. The two failure modes — *the model is unsafe* and *the deployment is unsafe* — share infrastructure concerns but require different solutions.

We see this most clearly in prompt injection. Greshake et al.'s *Indirect Prompt Injection* (2023) framed the problem; subsequent work (Yi et al., 2023; Chen et al., 2024) has shown the surface to be both deeper and harder to bound than originally thought. The platform layer can apply guardrails (DLP, regex, semantic classifiers) on inbound prompts, can require structured-output gates on model responses, and can ratelimit egress to sensitive tools. None of that *fixes* a sufficiently-determined prompt injection — the model decides what to comply with. Layered defence buys time and reduces blast radius; it doesn't reduce probability to zero.

## Where infrastructure-layer safety research sits

Three open problems we think are well-suited to platform-level investigation, where running real production traffic at scale is more useful than simulated benchmarks:

- **Empirical action-space coverage.** What fraction of real incidents can be addressed by an action library of size N? At what N does the marginal coverage gain drop below the maintenance cost? We have an answer for our own incident corpus — N=9 gets meaningful coverage of the SRE incidents we've seen — but it's untested elsewhere.
- **Adversarial-precondition resistance.** A misaligned (or compromised) agent could omit safety preconditions to game its own risk score. Cross-validating preconditions with an independent auditor agent is one defence; it has not, to our knowledge, been formalised in the academic literature.
- **Operator calibration drift.** What signals indicate that an operator's risk-tolerance threshold has drifted past the calibration of the underlying agent? Failing to detect drift means the safety budget gets silently spent; the literature is thin here because the data is operator-private.

## How this connects to what we ship

The SRE agent is the most direct expression of these ideas in the product. Every action is constrained by a hand-curated library; every action is risk-scored on a four-component decomposition the operator can audit; every action above an operator-set threshold is gated for human approval. The infrastructure-layer view is also why the audit log on every administrative mutation is a feature, not a checkbox.

If you're working on safety from the platform side rather than the model side — write to us. The conversations we've had with model-safety researchers have largely treated the deployment layer as a black box; we'd rather it weren't.

## References

- Christiano, P. F., et al. (2017). *Deep Reinforcement Learning from Human Preferences*. NeurIPS.
- Bai, Y., et al. (2022). *Constitutional AI: Harmlessness from AI Feedback*. arXiv:2212.08073.
- Garcia, J., & Fernández, F. (2015). *A Comprehensive Survey on Safe Reinforcement Learning*. JMLR.
- Greshake, K., et al. (2023). *Not what you've signed up for: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection*. AISec Workshop.
- Bricken, T., et al. (2023). *Towards Monosemanticity: Decomposing Language Models with Dictionary Learning*. Anthropic.
