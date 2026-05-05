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
