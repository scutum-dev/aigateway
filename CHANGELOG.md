# Changelog

All notable changes to the Scutum platform are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-05-03

First customer-shippable release.

### Added — release plumbing
- **One-line installer**: `curl -fsSL https://scutum.dev/install.sh | sh` — verifies docker-or-podman, fetches the release-tagged compose file and license public key, generates fresh random secrets, drops a `scutum` operator CLI.
- **`scutum` operator CLI** (`scripts/scutum`) — 12 verbs: `up`, `down`, `restart`, `logs`, `ps`, `pull`, `upgrade`, `backup`, `restore`, `activate`, `license`, `exec`, `config`. POSIX `sh`, runs under `docker compose` or `podman-compose`.
- **`docker-compose.release.yaml`** — image-only customer-safe compose, no `build:` directives, references pre-built `ghcr.io/scutum-dev/scutum-*` images at the pinned `${SCUTUM_VERSION}`. 6 services up by default; optional `--profile sre|finops|observability|full` for the rest.
- **GitHub Actions release pipeline** (`.github/workflows/release-images.yml`) — on `v*` tag push, builds and pushes 7 multi-arch (amd64+arm64) service images to GHCR with both `:version` and `:latest` tags.

### Added — license enforcement
- **30-day trial / paid license validation** — Ed25519-signed JWTs verified offline against a public key bundled in the admin-api image. No phone-home.
- Migration 026: `licenses` table.
- `scripts/issue-license.py` CLI for the issuer (private key kept at `~/.scutum/`, gitignored).
- `GET /api/v1/license` (public) and `POST /api/v1/license/activate` (admin).
- 5-minute background revalidator so refreshed licenses take effect without restart.

### Added — SRE agent
- LLM-driven incident remediation with human-in-loop approval. Four trigger events (`provider.unhealthy`, `budget.exceeded`, `sla.violation`, `latency.spike`). Risk-scored 0-100 actions; profile-gated.

### Added — landing surfaces (scutum.dev internal only)
- B2B-positioned landing page at scutum.dev with comparison table, pricing tiers, research section, and a Cal.com-backed Book-a-Demo form.
- mkdocs-material docs site at scutum.dev/docs, brand-matched to the landing.
- Dedicated `marketing` Compose profile so these surfaces never deploy on customer infrastructure.

### Changed
- Rebranded "AI Control Plane" placeholder → **Scutum** across README, mkdocs, configs.
- `make up` is now customer-safe by default (6 services). `make up-marketing` adds the scutum.dev surfaces.
- Customer-facing docs reframe references from "the LiteLLM proxy" to "the Scutum proxy"; `LiteLLM Deep Dive` and `Agent Gateway Deep Dive` removed from the primary nav.

### Fixed
- Migration 007 cold-start race when `LiteLLM_SpendLogs` doesn't exist yet (LiteLLM creates that table at runtime via Prisma). Now skips view creation gracefully and `_ensure_cost_view` background task creates it once LiteLLM finishes booting.
- `transaction_per_migration=True` in alembic env so a transient failure in migration N doesn't roll back the chain.

### Compatibility
- Compose-spec compatible — runs unchanged under `docker compose`, `podman-compose`, or `nerdctl compose`. No Docker Inc commercial license required.

## [Unreleased]

### Added — chat.scutum.dev v0.2 (generative UI + hybrid search + GHA deploy)
- **Generative UI** — `render_artifact` tool lets the model emit interactive React components inline with answers. Curated react-live scope (React hooks + full Recharts primitive set, no `fetch`/`localStorage`/`document` access). Synthetic server-side `execute()` returns `{rendered: true}` so multi-turn replays don't fail AI SDK v6's tool-result validation. Charts, calculators, comparison tables, mini-explorers all work in a single chat turn.
- **Brave Search adapter + hybrid mode** — `lib/search.ts` now dispatches on `SEARCH_PROVIDER=tavily|brave|hybrid|none`. Hybrid runs both providers in parallel, dedupes by normalised URL (lowercase host + trailing-slash strip + fragment strip), round-robin interleaves so neither dominates the top-N. Recommended default.
- **Tavily MCP integration** (`lib/mcp.ts`, optional, off by default) — when `TAVILY_MCP_URL` is set, the model gets `tavily_search` / `tavily_extract` follow-up tools on top of the prefetched sources. System prompt instructs "use sparingly — 1–2 follow-ups."
- **GitHub Actions deploy workflow** — `.github/workflows/deploy-chat.yml` runs `vercel pull → vercel build --prod → vercel deploy --prebuilt --prod` on every push to `main` that touches `ui/chat/**`. Replaces Vercel Git auto-deploy, which Hobby plan doesn't support for private org-owned repos. Concurrency is `cancel-in-progress` so only the latest commit deploys; manual trigger via Actions tab.
- **Tool-call indicators in `Message.tsx`** — inline "🔍 Searched: …" / "✓ Read: …" badges for each MCP tool call, so users see what the model is doing mid-stream.

### Added — Scutum Research (chat.scutum.dev)
- **New product surface**: search-with-citations chat at [chat.scutum.dev](https://chat.scutum.dev), deployed on Vercel. Calls the Scutum gateway for the LLM (so every query lands in the audit log) and Tavily for the search step. Streams answers via Vercel AI SDK v6 with inline `[^N]` citations + footer source list.
- LiteLLM aliases `scutum-research` (Sonnet-class for chat) and `scutum-fast` (Haiku-class for classification / Quick mode) — defined in `config/litellm/config.yaml`. Retargetable without code changes.
- `ui/chat/` Next.js 16 + Tailwind 4 + AI SDK v6 app (~530 LoC, 14 files). React-markdown rendering with custom citation parser; auto-strip footnote-definition lines.
- `/v1/*` proxy added to landing nginx (`ui/landing/nginx.conf`) so `https://scutum.dev/v1/chat/completions` reaches LiteLLM through Cloudflare → landing-ui → litellm:4000.
- New docs page `/docs/guides/scutum-research/` with architecture, API surface, citations rendering, configuration, roadmap.

### Added — hosted-trial warm pool + magic-link
- **Warm pool fast path**: trial-provisioner keeps `WARM_POOL_MIN_SIZE` (default 3) Fly machines pre-booted and stopped. Verify-click → claim a `ready` slot → PATCH per-trial env → start machine → user in dashboard in **~1 minute** (vs ~10 min cold start). Tunables: `WARM_POOL_*` env vars on trial-provisioner. Slow path remains as fallback when pool is empty.
- Migration 029: `warm_machines` table (state machine: `warming → ready → claimed`, plus `failed → recycled`).
- Migration 028: per-trial `bootstrap_token`, `api_key`, `jwt_secret` columns on `trial_instances`.
- **Magic-link auto-login**: `/api/v1/trial-signup/{id}/status` returns `https://<id>.scutum.dev/admin/?bootstrap=<token>` on `active`. Admin-ui `Login.tsx` detects `?bootstrap=`, exchanges via new `POST /auth/bootstrap` endpoint, mints a JWT, drops user in dashboard. Token is one-shot (consumed-marker in `/tmp/`).
- **Welcome email** sent from `trial@scutum.dev` after a trial flips to `active` — contains the trial URL, persistent API key, and expiry date so users can log in from any device.
- **Golden-image bake** in `build-monolith.yml`: pulls + tarballs the 6 Scutum service images into the monolith image at build time. Per-trial cold start drops from ~7-min `docker compose pull` to ~30-sec `docker load` once the volume is warmed.

### Added — landing-page surfaces
- New "NEW · Scutum Research is here" pill above the hero linking to chat.scutum.dev.
- New "Built-in tools" section — 4 cards for Research (featured), Workflows, Playground, MCP/A2A.
- Hero CTA reorder: `Open Research` is now primary, `Try Now` secondary.
- Top nav adds `Open Research ↗` link to chat.scutum.dev.
- SEO: title, meta description, OG/Twitter tags now mention Scutum Research; sitemap adds `/try` and `chat.scutum.dev`; robots.txt registers chat.scutum.dev sitemap.

### Changed — reliability & boot-path hardening
- Trial-monolith Fly volume now mounts at `/var/lib/docker` (NOT `/data`). Anonymous Docker volumes were ephemeral on Fly machine updates → markers + image cache wiped on every claim → repeat 8-min docker-load. State markers + install bundle moved to `/var/lib/docker/scutum-state/`.
- Front-of-house nginx in monolith starts FIRST (before dockerd) so `:80` serves a `/booting` page during the slow boot instead of connection-refused.
- `entrypoint.sh` adds: 5-attempt compose-up retry, background dockerd + compose watchdog every 30s, SIGTERM trap for graceful shutdown.
- `entrypoint.sh` syncs host env → `config/.env` on every boot for the per-trial secrets — ensures `compose --env-file` reads the values that `claim_warm_machine` PATCHed onto the Fly machine, not the warmup placeholders that install.sh wrote on first boot.
- `litellm` healthcheck switched from `wget` (not in image) to `curl ‖ wget` fallback chain. Same change for `admin-ui` and `docs-site`. Removed cascading `condition: service_healthy` deadlocks.
- LiteLLM in trial monolith now starts with `--use_prisma_db_push` — skips the migrate-deploy retry loop that wasted ~6 min on every cold boot when Prisma found a non-empty schema.

### Changed — top nav + URL surface
- Landing nav reduced from 11 items to 6 (removed within-page anchor links).
- `chat.scutum.dev` Cloudflare CNAME proxied (orange cloud) with a Configuration Rule overriding zone-wide Flexible SSL → `Full` for that hostname only.

### Fixed — chat.scutum.dev
- `??` → `||` for URL/string env-var fallbacks in `app/layout.tsx` and `app/api/chat/route.ts`. Vercel's `vercel pull` returns blank values for defined-but-empty entries, which slip through `??` and reach `new URL("")` → `next build` fails at page-data collection for `/_not-found` with `ERR_INVALID_URL`.
- `@ai-sdk/openai-compatible` `^1` → `^2`. v1 is LanguageModelV2-only; the AI SDK v6 tool loop needs V3, so steps were terminating after the first tool call (the "specificationVersion compatibility mode" warning was the tell).
- `render_artifact` synthetic `execute()` — without a tool result, multi-turn replays failed with "Tool result is missing for tool call …" because the assistant's previous turn referenced a `toolCallId` with no matching tool-result message.
- Hybrid prefetch is the default search path again. With MCP search tools fully exposed, Claude over-searched on ambiguous queries (4 sequential `tavily_search` + 2 `tavily_extract` on "Vercel Ship 2025" before exhausting `MAX_TOOL_STEPS=5`). Prefetch keeps sources deterministic and the model focused on writing.
- AI SDK v6 generic shape: `useChat<{messageMetadata: T}>` was wrong; correct is `useChat<UIMessage<T>>`.
- `package.json` `overrides.ai` set to `$ai` to dedupe the dual-version pull from `@ai-sdk/react`'s nested `ai` dependency.

### Fixed — trial provisioning
- Fly Machines API field rename: `auto_stop_machines` → `autostop`, `auto_start_machines` → `autostart`. Old names were silently dropped → trials never auto-stopped, ran 24/7.
- `autostop=False` during warmup. Fly's edge proxy SIGTERMs warming machines at ~9 min ("excess capacity"), interrupting the docker-load mid-stream. Re-enabled at claim time so user trials still scale to zero.
- Catch Fly's `"uniqueness constraint violated"` 422 in `_is_already_exists` so partial provisioning failures resume idempotently.
- Bootstrap-marker path moved to `/tmp/` — admin-api runs as uid 1000 and `/etc/` is root-owned. Marker creation was permission-denied, validate_bootstrap_token returned None, all magic-link clicks 401'd.
- React Router `basename="/admin"` mismatch — landing on `/` rendered nothing. Front-of-house nginx now 302s `/` → `/admin/` and strips the `/admin/` prefix when forwarding to admin-ui.
- `BOOTSTRAP_TOKEN` env now forwarded into the admin-api container via the release compose `environment:` block. Without this admin-api saw `os.getenv("BOOTSTRAP_TOKEN", "")` as empty → 401.
- Fly autostop on warm machines fixed (rename + boolean form) — pool slots actually cycle to zero when idle.
- Pool warmer recycler SQL: `||` concat doesn't accept int4 without an explicit `::text` cast — caused an "invalid input for query argument" loop on every tick.
- Pool warmer throttled to `WARM_POOL_CONCURRENCY=1` (default) — parallel warmups multiplied failure blast radius (we burned 19 Fly machines in a 1.5h failure loop before adding the throttle).

### Added
- **Routing policies**: Fallback chains, model groups, routing strategy, and conditional rules — configured via Admin UI, synced to LiteLLM
- Migration 023 for `routing_policies` table
- New Admin UI page: Routing Policies with LiteLLM router status panel
- OpenAPI tag descriptions for all 24 router groups in Swagger/ReDoc
- Pydantic `Field()` descriptions across all enterprise router models
- CHANGELOG.md and CONTRIBUTING.md project documentation

### Changed
- **SSO/OIDC rewrite**: Full Authorization Code + PKCE flow replacing stub implementation (auth_sso.py)
- SSO test endpoint now performs real OIDC discovery against configured issuer
- A/B testing: wired traffic splitting weights to LiteLLM `/model/new`, added metric collection and auto-promote/rollback
- DLP: wired `scan_text_with_detectors()` utility and standalone `/scan` endpoint
- Model deprecations: wired `check_model_deprecation()` utility and `/sync-alias` endpoint for LiteLLM model aliases
- Prompt execution: integrated DLP scanning (blocks on match) and deprecation checks (blocks on sunset)

### Fixed
- Integration test module conflicts (config/routes/models) between services
- Ruff lint and format compliance across all source and test files
- Frontend TypeScript errors in test files (wrong property names, unused imports, void returns)
- Added `python3-saml` to requirements.txt for SAML support

## [1.2.0] - 2026-02-18

### Added
- **Enterprise features (14 new domains):**
  - Multi-tenancy: Organization → Business Unit → Team hierarchy with RBAC
  - SSO/OIDC: Per-organization provider configuration (authorize/callback stub)
  - Audit trail: Immutable logging of all admin actions with filtering and export
  - DLP: Content detectors (regex, keyword, PII) and team content policies
  - Prompt registry: Versioned templates with approval workflows, rendering, and LLM execution
  - Rate limiting: Granular per-user/team/model policies with RPM/TPM/RPD/TPD and burst
  - Model access governance: Tiered access with request/approval workflows and time-limited grants
  - Chargeback: Cost allocation rules, monthly reports from LiteLLM spend data, budget forecasting
  - SLA monitoring: Health metrics collection (5-min intervals), violation detection, failover rules
  - A/B testing: Variant registration in LiteLLM, lifecycle management (draft→running→completed)
  - Semantic cache management: Stats, entry lookup, settings sync to LiteLLM Redis cache
  - Event system: Subscription-based notifications (webhook, Slack) with event publisher
  - Playground sessions: Shareable prompt/model/settings persistence
  - Model deprecations: Deprecation notices with replacement suggestions and sunset dates
- 13 new Alembic migrations (010–022) for all enterprise tables
- `event_publisher.py` — real event dispatch pipeline (webhook + Slack channels)
- `auth_sso.py` — SSO/OIDC flow endpoints (stub implementation)
- `crypto.py` — Fernet encryption for SSO client secrets
- SLA health collector background task in `main.py` (queries LiteLLM_SpendLogs every 5 minutes)
- 11 new Admin UI pages with full TanStack React Query integration

## [1.1.0] - 2026-02-17

### Added
- A2A agent management UI and API with gateway sync
- Product deck (Reveal.js presentation)
- LiteLLM guardrails integration (Presidio PII + LLM Guard scanners)
- LiteLLM embeddings configuration
- Playground deployment to production
- Full team CRUD with guardrail profile assignment
- Guardrails documentation guide

### Fixed
- CI coverage threshold and Docker build context for shared library
- Unit test collection and execution failures in CI
- Security hardening, lint fixes, and accessibility improvements

## [1.0.0] - 2026-02-16

### Added
- Gateway sync: Admin API writes agentgateway config to shared volume / K8s ConfigMap
- MkDocs documentation site with quickstart, admin guide, and integration guides
- Workflow execution details page
- Infrastructure improvements (K8s manifests, Terraform)
- Open-source guardrails layer with LLM Guard and Presidio
- Semantic cache, cost predictor, and FinOps dashboard tabs in playground

### Changed
- Rebrand from "AI Gateway" to "AI Control Plane" across entire codebase

## [0.9.0] - 2026-02-05

### Added
- Initial platform release
- Admin API (FastAPI) with JWT auth, Alembic migrations, 10 base routers
- Admin UI (React 18 + Vite + TypeScript + Tailwind CSS) with 22 pages
- LiteLLM proxy configuration with 100+ models across 9 providers
- Agent Gateway integration with Cedar RBAC policies
- Workflow engine (LangGraph) with 3 templates (research, coding, data-analysis)
- A2A runtime (Temporal) with 5 agent workflow patterns
- Cost predictor with tiktoken counting and per-model pricing
- Budget webhook with 3-tier enforcement and multi-channel alerting
- FinOps reporter with cost reports, trends, and CSV/JSON export
- Docker Compose with profiles (default, observability, workflows, finops, full)
- Kubernetes manifests (Kustomize) with base + 4 overlays
- Terraform GCP deployment (GKE Autopilot, Artifact Registry, cert-manager)
- OpenTelemetry pipeline with Prometheus, Grafana (5 dashboards), and Jaeger
- Landing page with interactive LLM playground
- Multi-model comparison playground
- Production readiness checklist, security threat model, and deployment guides
- GPU stub service for clear error messages when local models unavailable
- Ollama support for local model deployment
