# Scutum Research

Perplexity-shaped chat with citations, deployed at [chat.scutum.dev](https://chat.scutum.dev). Calls the Scutum gateway for the LLM (so every query lands in your audit log + cost report) and Tavily for the web-search step.

## What it does

```
user types question
   ↓
/api/chat (Next.js route)
   ↓ search via Tavily
   ↓ inject sources into system prompt with [^N] citation markers
   ↓ stream from scutum.dev/v1/chat/completions (model: scutum-research)
   ↓
streaming answer with inline [^N] citations + footer source list
```

## Stack

- **Next.js 16** App Router + Turbopack
- **Vercel AI SDK v6** (`ai`, `@ai-sdk/react`, `@ai-sdk/openai-compatible`)
- **Tailwind v4**
- **Tavily** for web search (Brave/Exa easy swap in `lib/search.ts`)
- Backend = your existing Scutum gateway (`scutum.dev/v1`). No new server.

## Run locally

```bash
cd ui/chat
cp .env.example .env.local
# fill in SCUTUM_API_KEY (from your admin UI) + TAVILY_API_KEY
pnpm install     # or npm install
pnpm dev         # or npm run dev
```

Open <http://localhost:3000>.

## Deploy

Vercel project pointed at `ui/chat/` with the env vars from `.env.example` populated. CNAME `chat.scutum.dev` → the Vercel deployment.

```bash
# from the repo root, in ui/chat/
vercel link
vercel env pull .env.local
vercel deploy --prod
```

## Architecture decisions

- **Calls scutum.dev/v1, not provider APIs directly.** The whole point is that every query goes through the gateway: audit log, model routing, cost tracking. Bypassing it from the chat-ui server defeats the moat.
- **`scutum-research` is a LiteLLM alias**, not a real model. Defined in `config/litellm/config.yaml`. Resolves to `claude-sonnet-4-6` today; can be retargeted any time without changing chat-ui code.
- **Sources attached as `messageMetadata`** on the AI SDK stream so the UI panel and citation hyperlinks stay in sync with the streaming text.
- **Stateless for MVP.** Conversation lives in browser memory only. Refresh = fresh chat. Persistence + auth are the next milestones (see `.env.example` optional block).

## What's next (not built yet)

- [ ] Auth via Clerk (anon-friendly, sign-in to save threads)
- [ ] Persistence in Vercel Postgres / Supabase
- [ ] Rate limiting (Upstash) — required before going public
- [ ] **Pro Search** (multi-agent: planner → searchers → writer) using existing `src/workflow-engine`
- [ ] **Deep Research** (Temporal-backed) using `src/a2a-runtime`
- [ ] Domain restriction / source allowlist (enterprise feature)
- [ ] Embedded widget for Scutum trial dashboards
