# Quickstart

Get Scutum running on a Linux server (cloud VM, on-prem, k8s host) in under 5 minutes.

## Prerequisites

- **Docker Engine 20.10+** with the compose plugin, **or** **Podman 4.4+** with `podman-compose`. No Docker Desktop required — your install runs entirely on Apache 2.0 components, no Docker Inc commercial license needed.
- A **license JWT** from us. Trial keys are free for 30 days — email [hello@scutum.dev](mailto:hello@scutum.dev) or [book a demo](https://scutum.dev/) and we'll send you one.
- At least one provider API key (OpenAI, Anthropic, Google, xAI, DeepSeek, Bedrock, Azure, or Vertex).

## 1. Install

```bash
curl -fsSL https://scutum.dev/install.sh | sh
cd scutum
```

The installer:

- Verifies your container runtime
- Drops a versioned `docker-compose.yaml`, the `scutum` operator CLI, the `.env` template, and the license public key into `./scutum/`
- Generates fresh random secrets for `SCUTUM_API_KEY`, `JWT_SECRET_KEY`, `INTERNAL_SERVICE_KEY`, and `POSTGRES_PASSWORD` so production never ships with example values

To install a specific version into a different directory:

```bash
curl -fsSL https://scutum.dev/install.sh | sh -s -- --version 0.1.0 --dir /opt/scutum
```

## 2. Activate your license + provider keys

Open `config/.env` and paste:

```bash
LICENSE_KEY=eyJhbGciOiJFZERTQSI...   # the JWT we sent you

# At least one of:
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
```

The other secrets (`SCUTUM_API_KEY`, `JWT_SECRET_KEY`, `INTERNAL_SERVICE_KEY`, `POSTGRES_PASSWORD`) were already populated by the installer with fresh random values. `SCUTUM_API_KEY` is what your applications use to authenticate against the Scutum proxy on port 4000.

## 3. Start the platform

```bash
./scutum up
```

This pulls the pinned multi-arch images and brings up the customer-safe core:

| Service    | URL                        | Purpose                            |
|------------|----------------------------|------------------------------------|
| Scutum API | http://localhost:4000      | OpenAI-compatible LLM endpoint     |
| Admin API  | http://localhost:8086      | Configuration, audit, governance   |
| Admin UI   | http://localhost:5173      | Web admin console                  |
| Docs Site  | http://localhost:8089      | This documentation                 |
| PostgreSQL | localhost:5432             | Source of truth for config         |
| Redis      | localhost:6379             | Cache + rate limiting              |

Wait ~30 seconds for health checks to pass:

```bash
./scutum ps
```

## 4. Send your first request

The Scutum proxy is OpenAI-compatible — point any OpenAI client at port 4000 and authenticate with your API key.

```bash
# The installer wrote SCUTUM_API_KEY into your .env
KEY=$(grep ^SCUTUM_API_KEY config/.env | cut -d= -f2)

curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $KEY" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### Try a different provider

Switch models with one word — Scutum routes to the right provider:

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-haiku-4.5",
    "messages": [{"role": "user", "content": "One paragraph: what is the gateway pattern?"}]
  }'
```

### Try a model group alias

Group aliases route across provider families with automatic fallback:

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "fast", "messages": [{"role": "user", "content": "2+2?"}]}'
```

## 5. Open the Admin Console

Navigate to **http://localhost:5173** in your browser.

1. Enter your master key from `config/.env` and click **Sign In**.
2. The Dashboard shows today's request count, cost, and per-model usage.

From the sidebar:

- **Models** — all configured models, filter by provider, edit routing tiers
- **API Keys** — generate per-team and per-user keys with budgets
- **Teams / Organizations** — multi-tier hierarchy with SSO
- **Budgets** — soft and hard spending limits with alerts
- **Audit Log** — every config change, who, when, what
- **Prompts** — versioned templates with approval workflows
- **Rate Limits** — per-user, per-team, per-model
- **Model Access** — access tiers and approval workflows
- **Chargeback** — cost allocation per cost center
- **SLA Monitor** — provider health, p50/p95/p99 latency
- **A/B Tests** — model variants with traffic splitting
- **Events** — Slack, PagerDuty, email, webhook subscriptions
- **MCP Servers / A2A Agents** — agent gateway federation
- **Guardrails** — DLP, regex, semantic, model-based filters
- **Settings** — caching, cost tracking, routing policies
- **License** — verify your license state, days remaining, refresh

## Optional bundles

Default `./scutum up` runs the customer-safe core (6 services). Enable more via Compose profiles:

```bash
./scutum up --profile sre              # LLM-driven incident remediation, human-in-loop
./scutum up --profile finops           # Cost prediction + budget webhook
./scutum up --profile observability    # Prometheus + Grafana + Jaeger
./scutum up --profile full             # everything
```

## Day-to-day operation

```bash
./scutum ps                # service status
./scutum logs admin-api    # follow logs (any service name)
./scutum pull              # pull updated images at the same version
./scutum upgrade 0.2.0     # upgrade to a newer release
./scutum backup            # dump postgres to a timestamped .sql.gz
./scutum down              # stop everything (data preserved)
./scutum down -v           # stop and DELETE persistent volumes
```

For lower-level control, drop down to raw `docker compose` against the same `docker-compose.yaml`. Compose-spec compatible — works under `docker compose`, `podman-compose`, and `nerdctl compose` unchanged.

## Troubleshooting

**License says invalid or expired?** Run `./scutum license` to see the current state. Activate a refreshed JWT with `./scutum activate <new-jwt>` (no restart needed).

**A service is unhealthy?** Tail its logs:

```bash
./scutum logs admin-api
./scutum logs litellm
```

**Scutum proxy returning 401?** The `Authorization: Bearer` value must match `SCUTUM_API_KEY` in `config/.env`, or be a per-team / per-user key created from the Admin Console.

**Model returning errors?** Confirm the right provider API key is set in `config/.env` (e.g., Anthropic models need `ANTHROPIC_API_KEY`).

**Port conflicts?** Edit the port variables in `config/.env` (`LITELLM_PORT`, `ADMIN_UI_PORT`, `ADMIN_API_PORT`, `DOCS_SITE_PORT`).

## Next steps

- [API Integration Guide](./api-integration.md) — code examples in Python, TypeScript, Go, curl
- [Model Routing](./model-routing.md) — fallback chains, model groups, weighted policies
- [Cost Management](./cost-management.md) — budgets, alerts, FinOps reporting
- [Admin Guide](./admin-guide.md) — page-by-page console walkthrough
- [Licensing](../operations/licensing.md) — activate, refresh, troubleshoot
