# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A unified control plane that sits on top of **LiteLLM** (LLM proxy, port 4000) and **Agent Gateway** (MCP/A2A proxy, port 9000). PostgreSQL is the source of truth; the Admin API (FastAPI, port 8086) CRUDs all config and writes gateway YAML out via `src/admin-api/gateway_sync.py` to a shared volume that Agent Gateway hot-reloads. The Admin UI (React/Vite, port 5173) is the cockpit. LiteLLM and Agent Gateway each have their own built-in admin UIs — we proxy their APIs rather than reimplementing their features.

## Environment

- **All env vars live in `config/.env`**, not the repo root. `docker compose` is always invoked with `--env-file config/.env` (see Makefile `DOCKER_COMPOSE` var). `make init` copies `config/.env.example` → `config/.env`.
- Python 3.12, Node 20+, Docker Compose v2.
- Do not push to repo root `.env` — it is unused by the compose stack.

## Common commands

```bash
# Bring up services (profiles stack additively)
make up                  # customer-safe core: postgres, redis, litellm, admin-api, admin-ui, docs-site
make up-observability    # + otel-collector, prometheus, grafana, jaeger
make up-workflows        # + temporal, temporal-ui, workflow-engine, a2a-runtime
make up-finops           # + cost-predictor, budget-webhook
make up-sre              # + sre-agent
make up-marketing        # + landing-ui, landing-backend, deck-ui, playground-ui, trial-provisioner (scutum.dev only)
make up-full             # everything (including agent gateway, vault, nginx)
make down                # stop everything
make logs-litellm / logs-admin / logs-sre

# Database
make migrate             # alembic upgrade head inside admin-api container
make db-shell            # psql into postgres container
make db-reset            # DESTROYS data — prompts for confirmation

# Tests
make test                # cd tests && pytest -v
make test-unit           # pytest tests/unit/ -v  (no services needed)
make test-integration    # cost-predictor + budget-webhook API tests
make test-coverage       # unit + integration with HTML coverage
make test-frontend       # cd ui/admin && npm test (vitest)
python -m pytest tests/unit/test_auth.py::test_name -v   # single test

# Cloud (GCP + Terraform, see Makefile _deploy chain: _infra → _build → _wait → _seed)
make demo / staging / prod           # ENV-scoped deploys
make demo-destroy / staging-destroy  # teardown
make redeploy-k8s ENV=demo           # re-apply kustomize without rebuilding images
```

Raw `docker compose` always needs the env file: `docker compose --env-file config/.env ...`.

## Customer deploys vs scutum.dev marketing — STRICT BOUNDARY

Default `make up` is **customer-safe**: only platform services (postgres, redis, litellm, admin-api, admin-ui, docs-site). Customers should never see scutum.dev marketing.

The `marketing` profile gates everything scutum.dev-specific:
- `landing-ui` (the public scutum.dev page, including the `/try` signup at `ui/landing/try/`)
- `landing-backend` (Cal.com Book-a-Demo + verification email sender)
- `deck-ui` (sales presentation)
- `playground-ui` (demo playground)
- `trial-provisioner` (Fly + Cloudflare API caller for hosted trials — see "Hosted-trial flow" below)

Plus the env vars `CALCOM_*`, `DEMO_INBOX/FROM/REPLY_TO`, scutum.dev Resend SMTP creds — all must stay below the "scutum.dev MARKETING SURFACES" header in `.env.example` and only get set on the scutum.dev VM, never on customer envs.

**When adding a new service or env var, decide: is this platform infrastructure or scutum.dev marketing?** If marketing, add `profiles: ["marketing", "full"]` and put env vars in the marketing section of `.env.example`. If you find yourself adding scutum.dev-specific defaults (`@scutum.dev` addresses, Cal.com IDs, scutum.dev domain references) to a non-profile-gated service, you've crossed the boundary — back out and gate it.

`make up-marketing` brings up scutum.dev's full stack (used by `scripts/deploy-oci.sh`). `make up` brings up the customer-safe stack.

## Architecture: how a config change flows

1. User clicks something in Admin UI (`ui/admin`, React Query hooks in `src/api/hooks.ts` → `src/api/client.ts`).
2. Request hits Admin API (`src/admin-api/main.py`), routed to one of ~30 domain routers in `src/admin-api/routers/`.
3. Router auth-gates via `deps.require_admin` (mutations) or `auth.get_current_user` (reads), writes to Postgres with **asyncpg + parameterized SQL** (no ORM, no string interpolation), and calls `audit.log_audit_event()`.
4. For MCP/A2A/guardrail changes: `gateway_sync.py` materializes Postgres rows → `config.yaml` on the shared volume. LiteLLM/Agent Gateway file-watch and hot-reload.
5. Keys/teams/budgets/models routers are **proxies** to LiteLLM's own API — we do not duplicate that state.

## Service map (docker-compose profiles)

Core (customer-safe): `postgres`, `redis`, `litellm` (4000), `admin-api` (8086), `admin-ui` (5173), `docs-site` (8089).
`marketing` (scutum.dev only): `landing-ui` (9999), `landing-backend`, `deck-ui` (6002), `playground-ui` (6001), `trial-provisioner`.
`observability`: otel-collector, prometheus (9090), grafana (3030), jaeger (16686).
`workflows`: temporal, temporal-ui (8088), `workflow-engine` (8085, LangGraph), `a2a-runtime` (8087, Temporal agents).
`finops`: `cost-predictor` (8080, tiktoken/pricing), `budget-webhook` (8081, pre/post LiteLLM hooks), `finops-reporter`.
`sre`: `sre-agent` (incident-remediation agent).
`local-models`: `gpu-stub` (8090, Ollama-compat).
`infra`: vault, nginx.
`full` = all of the above + agent gateway (9000, admin UI 15000).

Other services in `src/` not always wired into compose: `gateway-abstraction` (provider-agnostic LLM SDK), `config-loader` (YAML hydration helper).

Custom Python services all share code via `src/shared/` (injected as docker build context `--build-context shared=./src/shared`). `src/` is on `sys.path` for tests via `tests/conftest.py`.

`docker-compose.override.{dev,staging,production}.yaml` layer on top of `docker-compose.yaml` for env-specific tweaks; the OCI deploy script picks the right override via `-f`. They are *not* picked up automatically by plain `make up` — only by deploy scripts.

## Code conventions (beyond what ruff/eslint check)

**Python (admin-api + services):**
- FastAPI, async/await throughout, asyncpg for DB. **No ORM** — raw parameterized SQL only.
- Every Pydantic field gets `Field(description="...")`.
- Auth: `require_admin` on mutations, `get_current_user` on reads.
- Always call `log_audit_event()` on create/update/delete.
- Imports grouped stdlib → third-party → local, alphabetical within groups.
- ruff config: `py312`, line-length 120, selects `E,F,I,W`.

**TypeScript (ui/admin):**
- React 18 functional + hooks. TanStack React Query for **all** server state (no Redux/Context for API data).
- Tailwind utility classes only; no custom CSS.
- All API types in `src/types/index.ts`; no `any`.
- API functions in `src/api/client.ts`, hooks in `src/api/hooks.ts`.
- Pages in `src/pages/`; each page has a co-located `.test.tsx`.

**Migrations:** Alembic from `src/admin-api/` — `alembic revision -m "…"`. Always write `upgrade()` + `downgrade()`. Seed data lives in the migration that creates the table (see `002_seed_models.py`, `003_seed_defaults.py`).

## Adding a feature end-to-end

1. Alembic migration in `src/admin-api/alembic/versions/`.
2. Router in `src/admin-api/routers/<feature>.py` with Pydantic models + endpoints.
3. `include_router()` in `src/admin-api/main.py` (note the existing `from routers import X as X_router` pattern).
4. Types in `ui/admin/src/types/index.ts`.
5. API funcs in `ui/admin/src/api/client.ts`, React Query hooks in `src/api/hooks.ts`.
6. Page in `ui/admin/src/pages/` + test file.
7. Route in `App.tsx`, nav entry in `Layout.tsx`.
8. **Decide profile gating** — is this customer-safe core, or does it belong behind `marketing` / `sre` / `finops` / `observability` / `full`? Profile-gate in `docker-compose.yaml` *and* in `docker-compose.release.yaml`.
9. **Decide tier gating** — if the feature is paid-tier-only, add a check via `license.current_state().feature_enabled("<flag>")`. The license JWT carries a `features` dict; trial unlocks everything for evaluation.

## Licensing (Ed25519, offline)

Every customer deploy needs a license JWT. Validation runs offline against a public key bundled in the admin-api image — no phone-home.

- **Public key**: `config/license-public.pem` (committed, also copied to `ui/landing/release/v*/license-public.pem` and into the admin-api image at `/app/config/`).
- **Private key**: `~/.scutum/license-private.pem` on the issuer's laptop ONLY. Gitignored. Never commit.
- **Mint a license**: `python scripts/issue-license.py --email X --tier {trial,team,business,enterprise} --days 30`.
- **Validator**: `src/admin-api/license.py` — soft-fail (expired/missing licenses never crash admin-api). Loaded in lifespan from `LICENSE_KEY` env → `licenses` table → none. Background task re-validates every 5 min.
- **Endpoints**: `GET /api/v1/license` (public, for UI activation prompt) and `POST /api/v1/license/activate` (admin, for in-place rotation).
- **Migration**: 026 created `licenses` table. Most-recent active row is operative. (See `src/admin-api/alembic/versions/` for the latest revision number — don't pin it in docs.)

## Hosted-trial flow (`/try` → Fly machine)

Marketing-profile-only feature for the public scutum.dev funnel. **Customers running their own Scutum do not get this** — the whole pipeline is gated behind the `marketing` profile.

End-to-end flow:
1. Visitor fills the form at `ui/landing/try/index.html` (Cloudflare Turnstile bot-check).
2. `POST /api/v1/trial-signup` (router `src/admin-api/routers/trial_signup.py`) creates `users` + `organizations` + `trial_instances` rows in `pending_verification`, sends a verification email via `landing-backend`'s Resend SMTP creds.
3. Verification link → `GET /api/v1/trial-signup/{id}/verify?token=...` flips status to `provisioning` and emits `pg_notify('trial_provision', trial_id)`.
4. `src/trial-provisioner/` (FastAPI + asyncpg LISTEN loop) consumes the notify and calls Fly + Cloudflare APIs in sequence: `fly apps create` → `fly volumes create` → `fly machines create` (image: `ghcr.io/scutum-dev/scutum-monolith:<ver>`) → `fly certs create` → Cloudflare CNAME for `<id>.scutum.dev`. On success, sets `fqdn` + `fly_app_name`, flips status to `active`, stamps `expires_at = now() + TRIAL_LIFETIME_DAYS` (default 30).
5. The `/try` page polls `GET /api/v1/trial-signup/{id}/status` while waiting.
6. A lifecycle scheduler (in trial-provisioner) scans `(status, expires_at)` to send 3-day reminder emails and to delete past-expiry trials. Deleted rows are retained with `status='deleted'` for funnel attribution.

Per-trial machine image: `infra/fly-monolith/` — single `docker:dind`-based image that runs the **entire** customer release compose inside one 2GB Fly VM (postgres + redis + litellm + admin-api + admin-ui + nginx, all sharing one OS). Front-of-house nginx maps `/` → admin-ui, `/api/*` → admin-api, `/v1/*` → litellm, `/docs/*` → docs-site. Cold-start (auto-stopped machine waking) is ~30–60 s while dockerd + containers boot. Built by `.github/workflows/build-monolith.yml`.

DB schema: migration 027 created `trial_instances` with the lifecycle states `pending_verification → provisioning → active → expired | deleted | failed`.

Env vars (trial-provisioner only): `FLY_API_TOKEN`, `FLY_REGION` (default `iad`), `FLY_VOLUME_GB` (default 5), `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ZONE_ID`, `TRIAL_BASE_DOMAIN` (default `scutum.dev`), `TRIAL_LIFETIME_DAYS` (default 30), `MACHINE_IMAGE` (override the per-trial image — useful in staging). All under the marketing section of `.env.example`.

Operator escape hatches:
- Failed provisions: row stays at `status='failed'` with `provision_error` populated. Manually clean up via Fly + Cloudflare dashboards, then flip back to `provisioning` and re-emit the NOTIFY to retry.
- Fly shared-cpu machines cap at 2GB/vCPU — `FLY_VM_CPUS` is auto-derived from memory in the provisioner (see commit `fa4925b`).
- Fly LE certs need a DNS-01 validation CNAME; provisioner adds it automatically (commit `0874872`).
- Fly storage driver: monolith image needs `fuse-overlayfs` (not the default `vfs`/`overlay2`) for nested-VM support (commit `1869198`).

## Release & customer distribution

The customer-shippable surface is **separate** from the dev clone path. Customers never `git clone` — they run `curl -fsSL https://scutum.dev/install.sh | sh`.

| Path | What it is | Who edits it |
|---|---|---|
| `docker-compose.yaml` | Dev compose with `build:` directives, all profiles | contributors |
| `docker-compose.release.yaml` | Image-only customer compose, references `ghcr.io/scutum-dev/scutum-*:${SCUTUM_VERSION}` | release-engineering — keep in lockstep with the dev compose for env vars |
| `scripts/install.sh` | POSIX-sh installer hosted at `https://scutum.dev/install.sh` | only edit when changing the install UX |
| `scripts/scutum` | 12-verb operator CLI (up/down/logs/upgrade/backup/etc.) shipped to customers | edit when adding a verb |
| `ui/landing/release/v0.1.0/` | Versioned mirror of install.sh, scutum CLI, compose, .env template, license public key — **served from scutum.dev** because the repo is private and `raw.githubusercontent.com` 404s for unauth | bumped on each release tag |
| `.github/workflows/release-images.yml` | On `v*` tag push, builds 7 multi-arch images (amd64+arm64) and pushes to GHCR with `:version` and `:latest` tags | edit when adding a service that needs an image |

**Flow when cutting v0.X.Y**:

1. Bump examples + version refs in code that hardcodes `0.X.Y`.
2. Copy current files into `ui/landing/release/v0.X.Y/` (symlink doesn't work — Docker COPY follows but the rsync to OCI may not preserve).
3. Update `ui/landing/nginx.conf`'s redirect target to v0.X.Y.
4. `git tag -a v0.X.Y -m "..."` and push the tag — GHA workflow publishes images.
5. Verify pull: `docker pull ghcr.io/scutum-dev/scutum-admin-api:0.X.Y` (requires the package to be public — flip in GitHub UI per package).
6. Smoke-test `curl -fsSL https://scutum.dev/install.sh | sh` on a fresh dir.
7. `gh release create v0.X.Y` with the changelog body.

**Customer-facing env var name**: `SCUTUM_API_KEY` (not `LITELLM_MASTER_KEY`). The litellm container internally still reads `LITELLM_MASTER_KEY` — `docker-compose.release.yaml` translates: `LITELLM_MASTER_KEY: ${SCUTUM_API_KEY:-${LITELLM_MASTER_KEY:-}}`. Customer never sees the legacy name.

## PR / commit conventions

Conventional commits: `feat:`, `fix:`, `docs:`, `ci:`, `refactor:`. Branch names: `feat/…` or `fix/…`. Squash-merge. Pre-commit runs `ruff --fix` + `ruff-format` (see `.pre-commit-config.yaml`).

## Gotchas

- `config/litellm/config.yaml` is ~1070 lines defining 100+ models across 9 providers; edit carefully.
- Cedar policies for Agent Gateway live in `config/agentgateway/policies/`.
- `init-db.sql` is the full schema for first-boot; Alembic takes over for subsequent changes. Keep them in sync only when introducing a brand-new table.
- Feature flags: `config/feature-flags/{base,dev,staging,production}.yaml`.
- Production domain: `scutum.dev` (deployed on an OCI Always Free ARM VM at `161.118.178.104`, behind Cloudflare Flexible TLS).
- Daily Postgres backups on the OCI VM via `~/scutum-backups/pg-dump.sh` cron at 03:17 UTC, 14-day retention + weekly archives.
- `.gitleaks.toml` allowlists `$LITELLM_KEY` and `sk-generated-key-\d+` in `docs/`, `examples/`, `tests/`, `scripts/`, `ui/landing/index.html` — real secrets elsewhere will still fail the hook.
- GCP deploy from Apple Silicon builds with `--platform linux/amd64` automatically (Makefile `_build` target).
- Migration 007 (`cost_tracking_daily` view) races with LiteLLM's Prisma init on cold-boot — handled defensively (skip-if-table-missing + savepoint + `_ensure_cost_view` background recovery in admin-api). Don't add similar dependencies on LiteLLM-managed tables without the same defensive pattern.
- Container images for the customer release are at `ghcr.io/scutum-dev/scutum-*:<version>`. Will move to `ghcr.io/scutum-dev/scutum-*` once the GitHub org is claimed — use `${{ github.repository_owner }}` in CI not a hardcoded owner.
- `nginx.conf` location ordering matters: prefix locations with `^~` modifier win over regex. The `/docs/` and `/release/` proxies need `^~` to beat the asset-extension regex (`\.(js|css|png|...)$`); without it, asset requests under those paths get hijacked.
- The repo is **private**. Customer-installable artifacts (install.sh, scutum CLI, release compose, license public key, env template) are mirrored to `ui/landing/release/v*/` so they ship from scutum.dev — `raw.githubusercontent.com` 404s for unauthenticated pulls.
