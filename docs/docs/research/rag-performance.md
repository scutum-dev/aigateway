---
title: RAG Performance — measurement at the proxy layer
hide:
  - navigation
---

# RAG Performance

**Scutum Research · 2026**

The original RAG paper (Lewis et al., 2020) treated retrieval-augmented generation as a single end-to-end system: retriever and generator trained jointly, evaluated on the final answer. Production RAG systems look nothing like that. They're heterogeneous pipelines — multiple retrieval backends, custom rerankers, prompt templates that mediate between retrieval output and model input, increasingly model-side reasoning over retrieved content. The research literature has, mostly, kept up: Asai et al.'s *Self-RAG* (2023), the reranking and late-interaction work (ColBERT, Khattab & Zaharia 2020), and the more recent *RAG-as-search* lines (Mavromatis et al., 2024) treat RAG as a composite system worth studying as such.

What's still missing is **end-to-end measurement** at production fidelity. Most published RAG numbers come from offline benchmarks against canonical datasets (NQ, TriviaQA, HotpotQA). Production retrieval quality is usually measured per-application, with custom evals, and rarely cross-published. Infrastructure that sees every retrieval and every model response is in a position to fix this — and we'd argue it's where the most useful next round of RAG research lives.

## What proxy-layer RAG measurement makes possible

When the platform proxies the model call, it sees:

- **The user's original query.**
- **The retrieved documents** (when retrieval happens via an MCP server registered with the agent gateway, or via a tool call observable through traces).
- **The final prompt** that hit the model.
- **The model's response.**
- **Any user feedback** (thumbs-up/down, downstream task success/failure).

That's the full data needed for end-to-end RAG evaluation. Specifically:

- **Recall@K** of the retrieval step (was the relevant document retrieved?). Measurable by labelling whether the response was correct *and* whether retrieval contained the supporting evidence.
- **Faithfulness** of the model's response to the retrieved evidence. Measurable by NLI-style entailment between the response and each retrieved chunk.
- **Answer correctness** on the user's original question. Measurable by user feedback or by an LLM judge.

None of this is novel as evaluation methodology. What's novel is that an AI proxy is **the natural place to measure all four jointly**, on production traffic, across heterogeneous retrieval backends. Per-application evals miss the cross-cut; per-retrieval-system evals miss the model-side faithfulness. The proxy sees both ends of the pipe.

## Why the literature isn't there yet

Two reasons:

**RAG benchmarks measure a single stack.** RAGAS (Es et al., 2023), TruLens, and the various LangChain eval libraries are correct but operate on one application's prompts at a time. They give you a number for *your* RAG; they don't give you a comparison across retrieval backends or across models on the same retrieval substrate.

**Production data is private.** The retrieval-quality data that would let us answer "is BGE-M3 better than text-embedding-3-large for code-search workloads?" exists, but it's locked in individual production deployments. No one publishes it because there's no shared substrate, no cross-vendor incentive, and the data is sensitive. An AI proxy is one of the few pieces of infrastructure that *could* collect this kind of data with operator consent and publish anonymised aggregates.

## Where Scutum sits

The agent gateway treats MCP servers as first-class objects. When an MCP server is configured as a retrieval backend (semantic-search, vector-DB-backed, or hybrid), every tool call is observable through the same trace pipeline as direct LLM calls. The cost predictor sees the per-call cost; the audit log sees the request shape; the proxy sees the final response.

That gives us infrastructure for the measurement work without requiring the operator to instrument anything beyond their existing MCP setup. What we *don't* have yet — and where the research is — is the eval substrate that turns this raw trace data into RAG-quality benchmarks worth publishing.

## Open questions

**Cross-backend retrieval comparison.** If a customer is using a vector-store-backed MCP server, and could swap it for a hybrid keyword+vector backend, how would they know which is better for their workload? Today they wouldn't, without running both for a month. The proxy could A/B test.

**Faithfulness measurement at scale.** Running NLI entailment on every (response, retrieved-chunk) pair is expensive. A subsampled or selectively-triggered measurement (e.g., on responses flagged by a guardrail, or on responses where the model's confidence was low) is the right tradeoff. Open: what's the right trigger?

**Reranker evaluation.** Late-interaction rerankers (ColBERT, BGE-reranker-v2) consistently outperform bi-encoders for top-K retrieval, at meaningful inference cost. The cost-quality trade-off varies by domain in ways the literature hasn't characterised at production scale.

**RAG vs long-context boundary.** When does it pay to RAG rather than load the full document into a long-context model? The answer depends on retrieval recall, model long-context performance, query specificity, and cost. None of this is published as a decision rule; the proxy is the right place to learn it empirically.

**Multilingual retrieval.** Most published RAG evals are English. Cross-lingual retrieval (query in language A, corpus in language B) has different failure modes. An infrastructure layer with multi-tenant traffic across languages can measure this without designing it.

## How this connects to what we ship

MCP servers configured in the Admin Console show up in trace data with full request/response visibility. The cost predictor incorporates retrieval costs into the routing utility. Audit logs capture every tool call including retrieval. The semantic cache (which is itself an embedding-similarity step, conceptually adjacent to dense retrieval) shares evaluation infrastructure with RAG measurement.

What we'd like to ship next is the **eval-substrate layer**: per-team RAG-quality dashboards, A/B testing across retrieval backends, anonymised cross-customer aggregate benchmarks (with consent). This is where we think infrastructure-layer research can produce numbers that the rest of the field doesn't have access to.

If you're working on RAG evaluation methodology or on production-traffic retrieval analysis, write to us — [hello@scutum.dev](mailto:hello@scutum.dev). We have early data and would benefit from external eyes on the methodology.

## References

- Lewis, P., et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*. NeurIPS.
- Asai, A., et al. (2023). *Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection*. arXiv:2310.11511.
- Khattab, O., & Zaharia, M. (2020). *ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT*. SIGIR.
- Es, S., et al. (2023). *RAGAS: Automated Evaluation of Retrieval Augmented Generation*. arXiv:2309.15217.
- Mavromatis, C., et al. (2024). *G-Retriever: Retrieval-Augmented Generation for Textual Graph Understanding and Question Answering*. arXiv:2402.07630.
