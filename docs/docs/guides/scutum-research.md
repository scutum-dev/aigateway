# Scutum Research

Search-with-citations chat product, deployed at [chat.scutum.dev](https://chat.scutum.dev) for the public surface and embeddable inside any Scutum trial / customer instance via the same gateway.

Think Perplexity, but every query routes through your gateway, every answer lands in your audit log, every model is one you've configured, and the whole thing can run inside your VPC.

## What it does

```
user types question
   ↓
chat.scutum.dev (Next.js + AI SDK v6 streaming UI)
   ↓
search the web via Tavily — top 5 results with snippets
   ↓
inject sources as numbered list in the system prompt
   ↓
stream from /v1/chat/completions on your gateway
       (model: scutum-research → routed to your chosen LLM)
   ↓
streaming markdown answer with [^1] [^2] inline citations
   ↓
sources panel below, every link auditable
```

## Why it's different from Perplexity

Perplexity is great for general consumers but problematic for enterprises:

| Concern | Perplexity Pro | Scutum Research |
|---|---|---|
| **Where queries land** | Perplexity's cloud | Your gateway, your audit log |
| **Self-hosted** | Not really — "Enterprise" runs on their infra | Yes, in your VPC |
| **Provider keys** | Theirs | Yours, configured in your gateway |
| **Pricing** | $20/seat/mo, flat | Per-query LLM cost, transparent |
| **Model swap** | Limited to their menu | Any of your 100+ configured models |
| **Customization** | None | Domain allowlist, RBAC per tenant, prompts |
| **Audit trail** | Limited | Same audit table as every other API call |

If you have analysts asking questions of the web all day, every query going through *someone else's cloud* is a real concern. Scutum Research solves that — and reuses the gateway you'd buy anyway.

## Two surfaces

**1. Public — `chat.scutum.dev`**

Anyone can hit this URL, no signup, rate-limited at the Cloudflare edge. It runs on Vercel, calls our hosted gateway (`scutum.dev/v1`) for the LLM, and uses Tavily for search. Free for casual use; if you want it self-hosted, see option 2.

**2. Self-hosted — embedded in your Scutum instance**

The same Next.js app, deployed alongside your Scutum stack. Set `SCUTUM_API_URL=https://your-scutum.example.com/v1` and your customers' queries never leave your network.

## How to use it from any OpenAI-compatible client

Scutum Research is exposed as a model alias in your LiteLLM config. Any client that speaks OpenAI's chat-completions API can call it:

```bash
curl https://your-scutum/v1/chat/completions \
  -H "Authorization: Bearer $SCUTUM_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "scutum-research",
    "messages": [
      {"role": "user", "content": "Latest changes to Vercel function pricing in 2026?"}
    ],
    "stream": true
  }'
```

The model alias resolves to the underlying model you've configured (Claude Sonnet 4.6 by default; swap in `config/litellm/config.yaml`). The chat UI at `chat.scutum.dev` calls this same alias.

There are also two related aliases:

- **`scutum-research`** — default for chat, tuned for "answer + citations" style. Sonnet-class.
- **`scutum-fast`** — cheap+fast lane (Haiku-class). Use for intent classification, follow-up disambiguation, or "Quick mode" where reasoning depth isn't critical.

## Architecture

```
┌────────────────────────┐                    ┌────────────────────────────┐
│  chat.scutum.dev       │                    │  Your Scutum gateway        │
│  (Next.js, Vercel)     │                    │  (LiteLLM @ your /v1/...)  │
│                        │                    │                            │
│  ┌──────────────────┐  │                    │  ┌──────────────────────┐ │
│  │ /api/chat        │──┼─search─►Tavily     │  │ scutum-research      │ │
│  │  route handler   │  │                    │  │ alias → claude-sonnet│ │
│  │                  │──┼──/v1/chat/───►─────┼─►│                      │ │
│  │  + AI SDK v6     │  │   completions      │  │  (audit log entry)   │ │
│  │    streaming     │  │   (auth: bearer)   │  │  (cost tracking)     │ │
│  └──────────────────┘  │                    │  └──────────────────────┘ │
│           │            │                    │                            │
│           ▼            │                    │                            │
│   user's browser       │                    │                            │
│   streaming response   │                    │                            │
│   with [^N] citations  │                    │                            │
└────────────────────────┘                    └────────────────────────────┘
```

The chat app is **stateless** — no chat history persistence in v0, no auth. Conversations live in browser memory. (Both come back with auth + a Postgres-backed thread store; deferred until product-market-fit signal.)

## What's coming next

- **Pro Search** (multi-agent: planner → parallel searchers → writer + critic) using your existing `workflow-engine` LangGraph templates
- **Deep Research** (Temporal-backed, durable across crashes, ~5 min reports) via `a2a-runtime`
- **Embedded chat panel in trial dashboards** so trial users can sample Research on their own instance immediately
- **Domain allowlist** per tenant — useful for regulated customers ("only allow searches against `nih.gov, pubmed.gov`")
- **Source-diversity check** — critic ensures answers cite ≥3 distinct domains to reduce echo-chamber bias

## Configuration

Aliases for the chat product live in `config/litellm/config.yaml`:

```yaml
- model_name: "scutum-research"
  litellm_params:
    model: "claude-sonnet-4-6"
    timeout: 180
  model_info:
    id: "scutum-research"
    mode: "chat"

- model_name: "scutum-fast"
  litellm_params:
    model: "claude-haiku-4-5"
    timeout: 60
```

Swap the underlying `model:` to retarget without changing chat-ui code.

The chat-ui itself (env vars in `ui/chat/.env.example`) needs:

| Var | Purpose |
|---|---|
| `SCUTUM_API_URL` | Where to call (your gateway's `/v1`) |
| `SCUTUM_API_KEY` | Bearer for the gateway. Use a chat-scoped key with a monthly budget cap, not the master |
| `SCUTUM_DEFAULT_MODEL` | Defaults to `scutum-research` |
| `SEARCH_PROVIDER` + `TAVILY_API_KEY` | Which search service to use, and credentials |
| `NEXT_PUBLIC_APP_URL`, `NEXT_PUBLIC_SITE_NAME` | Public branding |

Rate limiting: handled at the Cloudflare edge, not in the app. Configure under Rules → Rate limiting; e.g. 10 req/min/IP on `/api/chat`. Free CF plan supports 1 rule + 10k matched requests/month, plenty for an MVP.

## Citations: how they work

The system prompt instructs the model to cite sources as `[^N]` matching a numbered list. The UI's markdown renderer turns each `[^N]` into a small superscript link → the source URL. A footer panel shows the full source list.

Hallucinated citations (a `[^7]` when only 5 sources were retrieved) render as plain `[7]` text without a link, so the user can spot them. A future Pro Search mode adds a critic agent that strips invalid citations before the answer reaches the user.

## Source code

- Chat UI: `ui/chat/` in the [main repo](https://github.com/scutum-dev/aigateway)
- Model aliases: `config/litellm/config.yaml`
- Server-side route: `ui/chat/app/api/chat/route.ts`

The whole thing is ~530 lines of TypeScript on top of the gateway you already run.
