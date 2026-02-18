# Contributing to AI Control Plane

Thank you for your interest in contributing! This guide covers development setup, coding standards, and the pull request process.

## Development Setup

### Prerequisites

- Docker and Docker Compose v2
- Python 3.12+
- Node.js 20+ and npm
- Make

### Quick Start

```bash
# Clone and start core services
git clone <repo-url> && cd gateway
make up

# This starts: PostgreSQL, Redis, LiteLLM, Admin API, Admin UI, Landing UI, Deck, Docs Site, Playground
# Admin UI: http://localhost:5173
# Admin API: http://localhost:8086/docs (Swagger)
# LiteLLM: http://localhost:4000
```

### Service Profiles

```bash
make up                  # Core services only
make up-observability    # + OTEL, Prometheus, Grafana, Jaeger
make up-workflows        # + Temporal, Temporal UI, Workflow Engine, A2A Runtime
make up-finops           # + Cost Predictor, Budget Webhook
make up-full             # Everything
```

### Environment Configuration

All environment variables live in `config/.env` (not the repo root). Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `LITELLM_MASTER_KEY` | `$LITELLM_KEY` | Master API key for LiteLLM |
| `DATABASE_URL` | `postgresql://litellm:litellm@postgres:5432/litellm` | PostgreSQL connection |
| `REDIS_URL` | `redis://redis:6379` | Redis connection |
| `JWT_SECRET_KEY` | (generated) | JWT signing secret |
| `ENVIRONMENT` | `development` | `development`, `staging`, or `production` |

## Project Structure

```
src/
  admin-api/          # FastAPI admin API (port 8086)
    routers/          # One file per feature domain
    alembic/          # Database migrations
  workflow-engine/    # LangGraph workflows (port 8085)
  a2a-runtime/        # Temporal agent workflows (port 8087)
  cost-predictor/     # Token counting & pricing (port 8080)
  budget-webhook/     # Budget enforcement (port 8081)
ui/
  admin/              # React admin dashboard (port 5173)
  landing/            # Marketing page + playground (port 9999)
  playground/         # Multi-model comparison tool
config/
  litellm/            # LiteLLM config + guardrail handler
  agentgateway/       # Cedar policies and config
  .env                # Environment variables
```

## Coding Standards

### Python (Backend)

- **Framework:** FastAPI with async/await throughout
- **Database:** Raw SQL with asyncpg (parameterized queries only — no string interpolation)
- **Models:** Pydantic BaseModel with `Field(description="...")` on every field
- **Auth:** All mutation endpoints require `require_admin`; all read endpoints require `get_current_user`
- **Audit:** Call `log_audit_event()` on all create/update/delete operations
- **Formatting:** Follow existing patterns — no strict linter enforced yet
- **Imports:** Group as stdlib → third-party → local, alphabetical within groups

### TypeScript (Frontend)

- **Framework:** React 18 with functional components and hooks
- **State:** TanStack React Query for all server state; no Redux/Context for API data
- **Styling:** Tailwind CSS utility classes; no custom CSS files
- **Types:** All API entities typed in `src/types/index.ts`; no `any`
- **API layer:** Functions in `src/api/client.ts`, hooks in `src/api/hooks.ts`

### Database Migrations

- Use Alembic: `cd src/admin-api && alembic revision -m "description"`
- Always include both `upgrade()` and `downgrade()`
- Add appropriate indexes for query patterns
- Seed data goes in the migration that creates the table

### Adding a New Feature

1. **Migration:** Create Alembic migration for new tables
2. **Router:** Add `src/admin-api/routers/<feature>.py` with Pydantic models + endpoints
3. **Register:** Import and `include_router()` in `main.py`
4. **Frontend types:** Add types to `ui/admin/src/types/index.ts`
5. **API client:** Add functions to `ui/admin/src/api/client.ts`
6. **Hooks:** Add React Query hooks to `ui/admin/src/api/hooks.ts`
7. **Page:** Create page component in `ui/admin/src/pages/`
8. **Route:** Add route in `App.tsx` and navigation in `Layout.tsx`

## Pull Request Process

1. **Branch:** Create a feature branch from `main` (`feat/description` or `fix/description`)
2. **Commits:** Use conventional commits: `feat:`, `fix:`, `docs:`, `ci:`, `refactor:`
3. **Test:** Run `make test` before submitting (unit tests must pass)
4. **PR description:** Include a summary, test plan, and screenshots for UI changes
5. **Review:** All PRs require at least one approval before merge
6. **Merge:** Squash-merge to keep history clean

## Running Tests

```bash
make test              # All unit tests
make test-integration  # Integration tests (requires running services)
make lint              # Linting
```

## Getting Help

- Check existing docs in `docs/` for architecture and operational guides
- API reference: http://localhost:8086/docs (Swagger UI) or http://localhost:8086/redoc
- Open an issue for bugs or feature requests
