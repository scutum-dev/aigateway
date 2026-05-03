---
title: Platform Internals — SRE Agent, Scaling, Semantic Cache
hide:
  - navigation
---

# Platform Internals: SRE Agent, Scaling, Semantic Cache

**Engineering whitepaper · Scutum · 2026**

!!! note "What this is"
    A walkthrough of three of Scutum's most operationally-meaty capabilities: how the SRE agent works in production, how the platform scales, and how the semantic cache is built. Other whitepapers cover the math behind specific subsystems; this one is the in-practice picture for an operator who wants to know what's actually happening inside the platform when traffic hits it.

## Part 1 — SRE agent in practice

The [risk-bounded remediation whitepaper](./risk-bounded-remediation.md) covers the math behind the agent's risk score. This section is the operational picture: what triggers the agent, what happens when it does, and what the operator sees.

### The triggering loop

Scutum publishes structured events to an internal bus from four sources: provider error-rate detectors (admin-api), budget breach hooks (budget webhook), SLA monitors (admin-api SLA collector), and latency-spike detectors (proxy traces). Each event has a typed payload and an originating service. The SRE agent subscribes to four event classes:

| Event | Source | Triggers when |
|---|---|---|
| `provider.unhealthy` | admin-api SLA collector | Error rate > 25% over 5 requests in a 5-minute window for any (provider, model) pair |
| `budget.exceeded` | budget webhook | Soft or hard budget cap breached for a team or org |
| `sla.violation` | admin-api SLA collector | p95 / p99 latency or success-rate target breached for a configured SLA contract |
| `latency.spike` | proxy traces | Provider response time > 3× the rolling 1-hour median for that (provider, model) pair |

When a subscribed event arrives, the agent constructs an *incident record* — a structured snapshot of platform state at the time of the trigger, plus the event payload. The incident is the unit of work; everything that follows references it.

### From incident to proposed action

The agent runs three steps sequentially, each instrumented:

1. **Diagnose** (~ 1–3 s). The configured LLM (default `claude-sonnet-4-6`) reads the incident record and produces a structured hypothesis: what changed, what the impact is, what evidence supports it. The diagnosis is itself stored on the incident record so the operator can audit the agent's reasoning later, even after auto-execution.
2. **Propose** (~ 1–2 s). Given the diagnosis, the LLM picks one action from the constrained action library (see the risk-bounded paper for the formal definition). The action arrives as a typed JSON object passing the action's schema.
3. **Score** (~ 50–800 ms). The risk score is computed via the four-component decomposition. The dry-run evaluator runs the action's preconditions against live state — this is the heaviest step, capped at 800ms; preconditions exceeding the budget are reported as `unknown` and treated as failures.

The total wall-clock from event arrival to scored proposal is typically 3–5 seconds. The agent is not in the data plane — incidents are processed asynchronously, on a queue, separate from the request path that triggered the underlying signal.

### The HITL gate, in practice

If the score is at or below the operator's threshold (default 40 in our shipping config), the action auto-executes and a notification posts to the configured channels (Slack, PagerDuty, email, webhook — your event subscriptions). Operators see the proposal post-fact in the Admin Console's SRE page, with full reasoning chain, score breakdown, and execution result.

If the score exceeds the threshold, three things happen *in parallel*:

1. The proposal lands in the **SRE Agent** page in the Admin Console with full reasoning, risk score breakdown, and a one-click approve / reject.
2. A notification fires through your configured event channels with a deep-link to the proposal.
3. The proposal is logged to the audit trail in `awaiting_approval` state.

When an operator approves, the action executes and the audit row updates. Reject — with an optional reason — closes the incident and logs the rejection. **Approvals are scoped to single proposals**; there is no "approve all" mode by design. The whole queue is auditable from the Admin Console with filters on status, source, action type, and time range.

### Why the constrained action library matters more than the LLM

The agent's safety profile is dominated by the closure of the action library, not by the LLM's reasoning quality. Three reasons:

- **Bounded blast radius.** Every action in the library has a hand-written upper bound on the entities it can affect. The agent fills in parameters; it cannot construct an action that affects something outside the library's bounds.
- **Schema validation pre-execution.** Even before the risk score, the parameters the LLM produces must pass the action's typed JSON schema. Hallucinated parameter names or wrong-typed values are rejected at parse time — the LLM doesn't get to "talk" the system into an invalid execution.
- **Inverse availability.** No action enters the library without a corresponding inverse (auto-revert, manual revert, or audit-log-trace-then-revert). This means every action the agent proposes is recoverable, by design.

The LLM is the *creativity layer* — picking which action and with what parameters; it is not the safety layer.

### What you'll see in the Admin Console

The SRE Agent page surfaces four views:

- **Incidents** — active and recently-closed incidents, sortable by status / source / severity / time. Each incident drills into the full reasoning chain.
- **Pending Approvals** — the queue of proposals awaiting human approval, one-click approve/reject from the list.
- **Manual Trigger** — a debug surface for replaying events against the agent. Useful for testing event subscriptions and observing the agent's behaviour against synthetic incidents.
- **Stats** — open incident count, MTTR, agent reachability indicator.

The agent itself is profile-gated (`--profile sre`) and tier-gated (Business and Enterprise license tiers only). On a Trial or Team license, the page renders an upgrade prompt instead of the agent surface.

## Part 2 — How Scutum scales

Self-hosted Scutum scales further than most operators expect on a single host before requiring fan-out. We've measured ~400 RPS sustained on a 4 vCPU / 16 GB host. The scaling shape past that single-host ceiling depends on which subsystem becomes the bottleneck first, and three patterns emerge in practice.

### The data plane (LiteLLM proxy)

LiteLLM's request-handling cost is mostly tokeniser + outbound HTTP to the provider. CPU pressure scales linearly with RPS. Memory is largely independent of RPS (the working set is a static price table + a small per-connection state).

The natural scaling pattern: **horizontal LiteLLM replicas behind a TCP load balancer**, sharing the same Postgres for spend logs and the same Redis for rate limiting. The replicas don't talk to each other. There's no leader, no consensus protocol, no shared state past the database. Adding a replica is one Compose / Kubernetes config line.

Limits:

- **Postgres write throughput** on `LiteLLM_SpendLogs` becomes the next bottleneck around ~3000 RPS sustained, depending on Postgres tier. Past that, partition `LiteLLM_SpendLogs` by time and increase the autovacuum aggressiveness on the most recent partition.
- **Per-provider rate limits** at the upstream APIs are usually the actual ceiling. Anthropic, OpenAI, and Google all gate at the API-key level; route different replicas through different keys via LiteLLM's per-key configuration to multiplex.

### The control plane (admin-api + admin-ui)

Admin-api is I/O-bound on Postgres, not CPU-bound. A single instance handles low-thousands of operator-facing operations per second. The most expensive endpoints are audit-log queries with date-range filters and the cost-tracking views that aggregate over the last 30 days.

Patterns we recommend, in order of when each becomes useful:

1. **Index your audit log queries**. Default schema has indexes on `(timestamp, actor_id)` and `(action, resource_type, timestamp)`. If you query by `org_id` heavily, add a composite index — it's a one-line migration.
2. **Read replicas for the audit-log endpoint specifically**. Audit reads are bursty (SOC 2 audit prep, compliance reviews); writes are steady. If you're reaching peak audit-read load, point only the read endpoints at a replica via PgBouncer routing.
3. **Multiple admin-api instances** are *unnecessary* for almost everyone. The throughput ceiling is far past what most deployments need. If you do need it (e.g., for HA across regions), the in-process state is small (gateway-config sync; cache; license state) and tolerates eventual consistency in practice.

### The integration plane (Agent Gateway, MCP, A2A)

Agent Gateway is itself a stateless Rust service; horizontal scaling is identical to LiteLLM. The relevant constraint is that *MCP server connections are stateful* (typically streaming subprocess pipes). When fanning out, ensure that each Agent Gateway replica can reach the MCP servers it needs — usually meaning each MCP server is itself either centralised or replicated.

A2A runtimes (Temporal-backed) scale independently via Temporal workers. This is well-documented Temporal territory; nothing Scutum-specific.

### The data layer (Postgres and Redis)

Postgres is the part of Scutum's stack most likely to need expert attention at scale. Two recommendations:

- **Use a managed Postgres** (RDS, Cloud SQL, Aurora, AlloyDB, Crunchy) past the point where you have meaningful traffic. The savings in operational toil are usually larger than the surcharge.
- **Partition the audit log table by month** if you keep more than ~12 months hot. The Postgres native LIST PARTITION feature works fine; no extension needed.

Redis is straightforward: 512 MB suffices unless your semantic-cache hit rate is high (in which case linear in unique cached prompts). Persist with AOF; cluster mode is unnecessary for most deployments.

### Multi-region

The platform tolerates being run as one stack per region with no cross-region coordination, sharing only the audit-log archival store (typically S3 / GCS in compliance mode). Operators see per-region Admin Consoles; correlating across regions is a query-layer problem solved by the archival store.

We do not currently ship a "global" Scutum that spans regions transparently. Most regulated buyers prefer the per-region pattern (data residency); most operators prefer it (simpler failure modes). If your use case actually requires global single-pane-of-glass, write to us.

## Part 3 — Semantic cache

Scutum ships an optional semantic cache that hits before the proxy forwards a request to a provider. It is **off by default**; operators turn it on per team or per route once they understand the privacy and correctness implications.

### How it works

For each request, before forwarding upstream:

1. **Embed** the prompt with a small, fast embedding model (we use `text-embedding-3-small` by default; configurable). This is a single ~30ms call; the embedding goes through the same proxy and counts toward the team's spend.
2. **Search** the team's cache index for the nearest cached prompt-embedding above a configurable similarity threshold (default cosine ≥ 0.97).
3. If a hit: return the cached response, marked as `x-scutum-cache: hit` in the response headers; do not call the upstream provider; do not bill against the team's request budget for the LLM call (only for the embedding call).
4. If a miss: forward to the provider. On response, store the (prompt-embedding, response) pair in the cache, scoped to that team and route.

The cache lives in Postgres with the `pgvector` extension; we use HNSW indexing for sub-millisecond k-NN. The single Postgres serves the whole platform's cache; it scales linearly until the index doesn't fit in RAM, at which point dedicate a Postgres for it.

### When to enable it, and when not

The cache is *correct* whenever the operator believes that small variations in the input prompt should produce the same response. Concretely:

- **Enable for**: FAQ-style chat where many users ask the same question slightly differently; product-description generation; classification tasks where the prompt template is stable; any high-volume endpoint where token cost is the dominant variable.
- **Don't enable for**: anything with personalisation in the prompt (the user's name, their data); anything with user-specific context that would make a stale response wrong; any safety-critical path where the cached response might miss real-time policy updates.

The cache is *team-scoped by default*; cross-team caching is opt-in (because team A's prompt might be confidential and team B shouldn't see the response). Even within a team, the operator can scope the cache to a specific route to bound the blast radius further.

### The PII boundary

Semantic similarity over embeddings does not respect PII semantics. Two prompts that say "What is John Smith's email?" and "What is Mary Jones's email?" can be cosine-close enough to hit the cache. **This is a real correctness problem** if either prompt contains real PII; a cached response from one user can leak to another.

The current shipping mitigation is: **DLP scanner runs first**. If the prompt matches a configured DLP detector (PII regex, custom patterns, or model-based classification), the request bypasses the cache entirely and goes straight to the provider. This is the simplest correct behaviour we could ship; it's not perfect (DLP detectors miss edge cases), and we recommend operators carrying real PII risk treat the cache as off-limits for any route that touches PII at all.

A more sophisticated boundary — embedding the prompt *with* the user-identity token so the cache key is implicitly user-scoped — is on the roadmap. It introduces a different failure mode (cache misses every time, defeating the purpose) and we're not happy with the trade-off yet.

### Operator-visible cache metrics

The Admin Console's Cache page surfaces:

- **Hit rate** per team and per route, time-windowed (last 24h / 7d / 30d).
- **Cost savings** as the difference between billed-LLM-cost-on-miss and billed-embedding-cost-on-hit, summed over the period.
- **Hit-rate decay** — does the cache get warmer over time, or are the prompts too varied to benefit?
- **Top cached prompts** — anonymised previews of the most-hit cache entries, useful for debugging and for noticing if a real PII pattern is being cached (in which case operator should disable the route's cache).

### What we don't ship yet

- **Cache invalidation by content change.** If you redeploy a system prompt that materially changes responses, the existing cached responses are stale. Operators must currently flush per-team or per-route by hand.
- **Cross-region cache sharing.** Each region's cache is local. Hot-path requests in region A don't benefit from region B's cache hits.
- **Adaptive thresholds.** The cosine threshold is fixed per route; one team's "close enough" is another's "different enough". Auto-tuning this from operator feedback is on the roadmap.

---

The three subsystems above are where most operators' questions about *what's actually inside Scutum* land. If you have a fourth that this paper missed — or want a deep dive on something we mentioned but didn't cover — write to [hello@scutum.dev](mailto:hello@scutum.dev). We expand this whitepaper as patterns emerge from operating the platform.
