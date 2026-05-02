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
make up                  # core: postgres, redis, litellm, admin-api, admin-ui, landing, deck, docs, playground
make up-observability    # + otel-collector, prometheus, grafana, jaeger
make up-workflows        # + temporal, temporal-ui, workflow-engine, a2a-runtime
make up-finops           # + cost-predictor, budget-webhook
make up-full             # everything (including agent gateway, vault, nginx)
make down                # stop everything
make logs-litellm / logs-admin

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
- `landing-ui` (the public scutum.dev page)
- `landing-backend` (Cal.com Book-a-Demo)
- `deck-ui` (sales presentation)
- `playground-ui` (demo playground)

Plus the env vars `CALCOM_*`, `DEMO_INBOX/FROM/REPLY_TO`, scutum.dev Resend SMTP creds — all must stay below the "scutum.dev MARKETING SURFACES" header in `.env.example` and only get set on the scutum.dev VM, never on customer envs.

**When adding a new service or env var, decide: is this platform infrastructure or scutum.dev marketing?** If marketing, add `profiles: ["marketing", "full"]` and put env vars in the marketing section of `.env.example`. If you find yourself adding scutum.dev-specific defaults (`@scutum.dev` addresses, Cal.com IDs, scutum.dev domain references) to a non-profile-gated service, you've crossed the boundary — back out and gate it.

`make up-marketing` brings up scutum.dev's full stack (used by `scripts/deploy-oci.sh`). `make up` brings up the customer-safe stack.

## Architecture: how a config change flows

1. User clicks something in Admin UI (`ui/admin`, React Query hooks in `src/api/hooks.ts` → `src/api/client.ts`).
2. Request hits Admin API (`src/admin-api/main.py`), routed to one of ~25 domain routers in `src/admin-api/routers/`.
3. Router auth-gates via `deps.require_admin` (mutations) or `auth.get_current_user` (reads), writes to Postgres with **asyncpg + parameterized SQL** (no ORM, no string interpolation), and calls `audit.log_audit_event()`.
4. For MCP/A2A/guardrail changes: `gateway_sync.py` materializes Postgres rows → `config.yaml` on the shared volume. LiteLLM/Agent Gateway file-watch and hot-reload.
5. Keys/teams/budgets/models routers are **proxies** to LiteLLM's own API — we do not duplicate that state.

## Service map (docker-compose profiles)

Core: `postgres`, `redis`, `litellm` (4000), `admin-api` (8086), `admin-ui` (5173), `landing-ui` (9999), `deck-ui` (6002), `playground-ui` (6001), `docs-site` (8089).
`observability`: otel-collector, prometheus (9090), grafana (3030), jaeger (16686).
`workflows`: temporal, temporal-ui (8088), `workflow-engine` (8085, LangGraph), `a2a-runtime` (8087, Temporal agents).
`finops`: `cost-predictor` (8080, tiktoken/pricing), `budget-webhook` (8081, pre/post LiteLLM hooks).
`local-models`: `gpu-stub` (8090, Ollama-compat).
`full` = all of the above + agent gateway (9000, admin UI 15000).

Custom Python services all share code via `src/shared/` (injected as docker build context `--build-context shared=./src/shared`). `src/` is on `sys.path` for tests via `tests/conftest.py`.

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

## PR / commit conventions

Conventional commits: `feat:`, `fix:`, `docs:`, `ci:`, `refactor:`. Branch names: `feat/…` or `fix/…`. Squash-merge. Pre-commit runs `ruff --fix` + `ruff-format` (see `.pre-commit-config.yaml`).

## Gotchas

- `config/litellm/config.yaml` is ~1070 lines defining 100+ models across 9 providers; edit carefully.
- Cedar policies for Agent Gateway live in `config/agentgateway/policies/`.
- `init-db.sql` is the full schema for first-boot; Alembic takes over for subsequent changes. Keep them in sync only when introducing a brand-new table.
- Feature flags: `config/feature-flags/{base,dev,staging,production}.yaml`.
- Production domain: `scutum.dev`.
- `.gitleaks.toml` allowlists `$LITELLM_KEY` and `sk-generated-key-\d+` in `docs/`, `examples/`, `tests/`, `scripts/`, `ui/landing/index.html` — real secrets elsewhere will still fail the hook.
- GCP deploy from Apple Silicon builds with `--platform linux/amd64` automatically (Makefile `_build` target).
