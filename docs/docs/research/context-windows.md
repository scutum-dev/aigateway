---
title: Context Window Management
hide:
  - navigation
---

# Context Window Management

**Scutum Research · 2026**

The "context window" debate has cycled through three positions in three years: scarce-resource (4k tokens, prompts must be terse), abundance-coming (128k+, paste everything), and back to scarcity-but-of-attention (Liu et al., 2023, *Lost in the Middle* — models can't reliably use long contexts even when they have them).

Each model generation has shifted the boundary, but the engineering question hasn't: **what should the platform do with a conversation that wants more context than the model handles well?** The answer matters because the platform sees every turn — the application doesn't always — and is therefore the right place to decide between long context, RAG, or cache.

## The decomposition we work with

Three reasons to extend a model's effective context, with different platform responses:

**Structural context.** A long instruction, a complex tool definition, a document the model needs to operate on cleanly from start to finish. Best served by *long-context loading* — pass the full content, accept the cost, hope the model attends to it. Mitigation: use a model with strong long-context performance (Anthropic's 200k window, Gemini 1.5's 1M, depending on benchmarks at the time).

**Reference context.** Facts the model needs that change over time — a customer's order history, a knowledge-base article, recent code from a repo. Best served by *retrieval-augmented generation* (Lewis et al., 2020) — fetch the relevant pieces at request time, paste them into a smaller context. The retrieval substrate is where MCP servers and vector stores live.

**Repeated context.** Identical or near-identical queries that should return the same response. Best served by *semantic caching* — embed the prompt, search a per-team cache, return the cached response on a hit. Bypass the model entirely.

The interesting platform claim is that these three are *not interchangeable*. They serve different reasons-for-extension, have different cost profiles, and have different correctness guarantees. The platform's job is to route a given request to the right pattern, not to pick one and apply it everywhere.

## Where each pattern fails

**Long context fails on attention degradation.** Liu et al.'s *Lost in the Middle* (2023) showed empirically what practitioners had suspected: information in the middle of a long context is reliably less attended-to than information at the start or end. Subsequent work (An et al., 2024; Kamradt's "needle in a haystack" benchmarks) shows the effect varies by model and degrades gracefully but doesn't go away. Long context is correct *on average* and silently wrong *in detail*.

**RAG fails on retrieval quality.** A perfect long-context model with bad retrieval is worse than an imperfect long-context model with full content. Asai et al.'s *Self-RAG* (2023) and reranking work (ColBERT, Khattab & Zaharia 2020) push the retrieval-quality boundary, but production RAG systems still drop facts that exist in the corpus and surface near-misses that derail the model. Operationally, retrieval-quality issues are silent — the model produces plausible-but-wrong output.

**Semantic caching fails on PII and on policy drift.** Two prompts that differ only in a customer's name can be cosine-close enough to share a cache entry. A response that was correct yesterday can be wrong today (the underlying policy shifted, the system prompt changed). The cache needs an operator to bound it, and the bounds are hard to get right (see the [Platform Internals](../whitepapers/platform-internals.md) whitepaper for the discussion).

## What the platform layer can do that the model can't

Three things the platform sees that the model doesn't:

- **The full conversation history**, including turns the application chose not to include in the current prompt. A platform that knows the full history can decide *whether the current turn needs retrieval*, not just *whether retrieval is configured*.
- **Cross-request structure**. If a team is asking the same kind of question repeatedly, the platform can detect that and warm the cache, or stand up a route-specific RAG index, without the application doing anything.
- **Cost and latency profiles per pattern**. Long context costs tokens; RAG costs retrieval round-trip and embedding compute; cache costs an embedding call (on miss) or near-zero (on hit). The platform sees the tradeoffs and can pick per-request.

The literature we draw from on context-window management is currently under-developed because most empirical work is single-pattern: pure long-context vs pure RAG vs pure cache. Hybrid systems are what production deployments actually want, and the design space hasn't been formally mapped.

## Open questions an infra-layer team is well-placed to investigate

- **Auto-routing between long-context, RAG, and cache.** Given a request, which pattern minimises cost-at-fixed-quality? The platform has the data (cost, latency, quality grades over many requests) to learn this empirically; we haven't shipped this yet.
- **Cache invalidation by content change.** When the system prompt or a knowledge-base article updates, every cached response that depended on the old version is now stale. v0.1 doesn't track this dependency; making it tractable is a graph problem on the (prompt → context-source) edges.
- **RAG quality measurement at the proxy layer.** End-to-end retrieval quality (did the right facts make it into the prompt? did the model use them?) is currently measured per-application, not per-platform. A proxy with full visibility into prompts, retrieved docs, and final responses is the right place to publish standardised RAG benchmarks across providers and retrieval backends.

## How this connects to what we ship

The semantic cache lives in the proxy with operator-tunable similarity thresholds and PII-aware bypass via the DLP detector. MCP servers register with the agent gateway and are observable through the same trace pipeline as everything else. Long-context routing is implicit in the routing-utility framing: cost-per-token scales linearly with input tokens, so the decision rule already prefers shorter prompts when other factors are equal.

What we don't yet ship is the **automatic-pattern-selection** layer that picks long-context vs RAG vs cache based on observed traffic. That's the highest-value research direction in this space and the one we'd most welcome external collaboration on.

## References

- Liu, N. F., et al. (2023). *Lost in the Middle: How Language Models Use Long Contexts*. arXiv:2307.03172.
- Lewis, P., et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*. NeurIPS.
- Asai, A., et al. (2023). *Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection*. arXiv:2310.11511.
- Khattab, O., & Zaharia, M. (2020). *ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT*. SIGIR.
- An, S., et al. (2024). *L-Eval: Instituting Standardized Evaluation for Long-Context Language Models*. arXiv:2307.11088.
