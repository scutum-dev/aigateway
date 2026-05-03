---
title: Best Practices for Self-Managed Scutum
hide:
  - navigation
---

# Best Practices for Self-Managed Scutum

**Engineering whitepaper · Scutum · 2026**

!!! note "Who this is for"
    Operators running Scutum on their own infrastructure — cloud VM, on-prem box, k8s cluster, OCI Always Free, anything that takes Docker Compose or Podman. This is the operational playbook: what to do on day one, what to set up before paying customers depend on the platform, and where to invest first if you're scaling past a single host.

This is opinionated. The goal is a deployment that an on-call engineer who didn't build it can keep running.

## Day one — the first 24 hours

The customer-install path (`curl -fsSL https://scutum.dev/install.sh | sh`) gets you to a healthy stack in under five minutes. What it does *not* set up: backups, monitoring, alerting, secrets rotation, log retention. Those are operator responsibilities. Don't put production traffic through Scutum until you've handled all six items below.

### 1. Move secrets out of `config/.env` immediately

The installer generates random values for `SCUTUM_API_KEY`, `JWT_SECRET_KEY`, `INTERNAL_SERVICE_KEY`, and `POSTGRES_PASSWORD`. They land in `config/.env` on the host filesystem with mode `0600`. That's *fine* for a single-host evaluation deployment; it is *not* fine for a deployment with more than one operator who shouldn't see all of them.

Two patterns work:

- **Secret manager + entrypoint mutation.** Mount the secrets manager's CLI in a sidecar that overrides `config/.env` at start time. Vault, AWS Secrets Manager, and GCP Secret Manager all have a working recipe in their docs.
- **Sealed-secrets / SOPS pattern**, if you're managing the deployment via GitOps. Encrypt `config/.env` with the deploy key, decrypt at deploy time, never commit plaintext.

Either way: rotate `JWT_SECRET_KEY` and `INTERNAL_SERVICE_KEY` on a quarterly cadence (`SCUTUM_API_KEY` only when it leaks, since it's also baked into customer applications).

### 2. Database backups, with restore tested

The most common Scutum failure mode is "Postgres data volume corrupts and we lose audit history." Defend against it on day one:

```sh
# As a host cron at 03:17 local time, daily:
docker compose --env-file config/.env exec -T postgres \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner \
  | gzip -9 > /var/backups/scutum-$(date -u +%Y%m%dT%H%M%SZ).sql.gz
```

Two things matter more than the cron:

1. **Off-host the backups.** A backup on the same VM is meaningless if the VM dies. Ship to S3, GCS, B2, or any object store with a cheap tier. 14-day daily rotation + indefinite weekly archives is a reasonable default.
2. **Restore-test once a quarter.** A backup you've never restored is a guess. Write a 30-line shell script that pulls the latest dump, restores it into a throwaway Postgres, runs `SELECT count(*) FROM audit_logs`, and emails you the diff. Run it on a calendar.

### 3. Watch the four signals

Forward all admin-api + LiteLLM logs to your existing log aggregator (Datadog, Loki, Splunk, CloudWatch — pick one). The four signals to alert on:

| Signal | Why it matters | Suggested threshold |
|---|---|---|
| Admin-api `/health` HTTP error rate | Platform-level outage | > 1% over 5 min |
| LiteLLM upstream provider error rate | Provider-side incident the SRE agent should already see | > 25% over 5 min, per provider |
| Postgres connection-pool exhaustion | Background tasks blocking the request path | `pg_stat_activity` connections > 80% of `max_connections` |
| `licenses` table active-row count = 0 OR expired | Platform running unlicensed (bug or expiry) | Any duration > 1 hour |

Scutum publishes events for the second and fourth via the event subscription bus — wire them to your existing PagerDuty/Slack subscription. The first and third are infrastructure-level, alert from your own platform monitoring.

### 4. Set realistic resource limits

The default Compose file ships generous limits for a single-host evaluation. For production, sizing depends on traffic. Rough guidance from our own benchmarks:

- **Postgres**: 2 GB RAM is enough up to ~100k requests/day. Past 1M requests/day, dedicate a managed Postgres (RDS, Cloud SQL); don't co-locate it with the app on the same host.
- **Redis**: 512 MB suffices unless you have an aggressive semantic-cache hit rate, in which case linear in unique cached prompts.
- **LiteLLM**: 4 workers handles ~400 RPS on a 4-vCPU box for chat completions. Scale workers, not host count, until you're past the box's ceiling — fan-out across hosts is a separate problem (see §"Beyond a single host" below).
- **Admin-api**: I/O-bound on Postgres. Sized for the slowest router (it's `/api/v1/audit-logs` with date-range filters); 50 connection pool, 4 workers is enough for most.

Set actual `mem_limit` and `cpus` in your Compose override; don't let the kernel OOM-kill arbitrary services under load.

### 5. Pin your release version

`docker-compose.release.yaml` references `${SCUTUM_VERSION:-0.1.0}`. **Pin it explicitly** in your `.env` and don't auto-update. The default won't surprise you across release versions, but the next person reading your config shouldn't have to know the default. Set `SCUTUM_VERSION=0.1.0` (or whatever you tested with) and treat upgrades as deliberate operations: stage a copy, run the migration there first, then upgrade prod.

### 6. License hygiene

A license JWT lives in two places: `LICENSE_KEY` in your `.env`, and the `licenses` row admin-api persisted on first boot. If your `.env` is in source control (GitOps), rotate the env-var reference to point at your secrets manager — committing a license JWT to git is no worse than committing any other long-lived credential, but treat it the same way.

When you renew (we email you 14 days before expiry), POST the new JWT to `/api/v1/license/activate`. No restart needed; the operative license rolls over and the old one stays in the table for audit.

## Operating beyond a single host

Single-host Scutum scales further than most operators expect — we've measured ~400 RPS sustained on a 4 vCPU / 16 GB host without breaking a sweat. But three signals tell you it's time to fan out:

- **Postgres is the bottleneck on writes.** `pg_stat_activity` shows long IDLE-IN-TRANSACTION rows, or connection-pool waits exceed 100ms p95. Move Postgres to a managed service or a dedicated host.
- **LiteLLM workers saturate before the box does.** `htop` shows LiteLLM at 100% across all assigned cores while the host has spare capacity. Scale to multiple LiteLLM replicas behind a load balancer; admin-api can stay single-instance for much longer.
- **You need geographic separation** — apps on multiple continents talking to one Scutum is fine for the proxy, painful for synchronous admin-api operations. Run an admin-api per region, point them at a multi-region Postgres (Neon, Aurora Global, AlloyDB), accept eventual consistency on audit reads.

The shape we recommend at scale is: managed Postgres + Redis at the data layer, multiple LiteLLM replicas behind a TCP load balancer, single admin-api (or one per region), shared object store for audit-log archives older than 30 days. That's the architecture our largest design-partner deployments run.

## Auditability — the hidden long-term liability

Scutum logs every administrative mutation to `audit_logs`. By default the table grows forever. Two things you'd ideally do before the table gets to a few hundred million rows:

1. **Retention policy.** Decide how long you keep audit data hot in Postgres vs. archived to S3. Trial: 30 days hot, archive forever. Business: 365 days hot, archive forever. Enterprise: 7 years hot. Configure via the `audit_retention_days` license feature (Enterprise tier ignores it).
2. **Partition by month** if you're keeping >1 year hot. Postgres `LIST PARTITION BY (date_trunc('month', timestamp))` — straight Postgres feature, no extension needed. Drop old partitions; archive the parquet to S3 first if compliance requires.

The cost of doing this on day one is fifteen lines of SQL. The cost of doing it after three years of unpartitioned audit growth is a maintenance window plus a vacuum-truncate dance under traffic.

## Upgrade procedure

A safe upgrade looks like:

1. **Stage**. Spin a copy of the current deployment with the same data. Run `./scutum upgrade <NEW_VERSION>` there first.
2. **Migration check**. The first thing the new version does is run alembic. Watch admin-api logs for migration completion before sending traffic. We engineer migrations to be cold-start-safe (see the [`007_replace_cost_tracking_with_view.py`](https://github.com/deosha/aigateway/blob/main/src/admin-api/alembic/versions/007_replace_cost_tracking_with_view.py) defensive pattern), but verify on your data.
3. **Smoke test**. Hit `/health`, `/api/v1/license`, `/v1/chat/completions` (one model per provider you care about), `/api/v1/audit-logs?limit=1`. All should return their expected shapes.
4. **Promote**. `./scutum upgrade <NEW_VERSION>` on production. Watch error rate for 30 minutes; rollback is `./scutum upgrade <OLD_VERSION>` if needed (data is forward-compatible across patch versions; minor versions document any breaking schema in the changelog).

Scutum tags only ever land on `main` after the matrix CI passes; you can read the published images' `org.opencontainers.image.version` label to verify what version is in your image registry.

## Disaster scenarios — what we recommend you practice

In our experience the three most common operator-pain moments are:

- **"The license expired and I didn't know."** With monitoring on the licenses table per §3 above, this is a 60-second response (POST the new JWT). Without it, the platform keeps running but the renewal banner in the UI is the only signal.
- **"Postgres ran out of disk."** Audit-log growth, semantic-cache growth, or the ill-timed combo of both. Set `pg_total_database_size` alerting at 70% of disk; partition the audit table per §"Auditability" above.
- **"A provider's API changed shape and our routes 500."** LiteLLM is downstream of provider API changes. Subscribe to LiteLLM's release notes; stage upgrades when a major version of LiteLLM ships.

Run a quarterly game-day where you simulate one of these. The operational muscle memory matters more than the alerts.

## What you should *not* spend time on

A few things operators try first that don't pay back:

- **Custom dashboards in Grafana** before you have shape on what the SLOs are. Use Scutum's bundled dashboards for the first month, write your own only when the bundled ones miss something specific.
- **Hand-tuning the SRE agent's risk weights** before observing how it behaves with defaults. The defaults are calibrated to err on the side of human-in-loop; you'll notice if it's too gated, and tuning is a five-minute config change.
- **Replacing components with your own**. Scutum runs LiteLLM, Postgres, Redis, OpenTelemetry — known good components composed deliberately. Substituting a different LLM proxy for LiteLLM voids most of the defensive design-work in this whitepaper. If you have a specific reason, talk to us.

## When to ask us

The platform is yours; we don't want to be in your loop on routine ops. We *are* in your loop for:

- **License rotation, tier changes, renewals** — `hello@scutum.dev`.
- **A novel incident class the SRE agent doesn't handle** — propose an action template; we'll prioritise it for the action library.
- **Compliance audit support** — SOC2, HIPAA, ISO. We provide the platform-side evidence; your auditor handles your application-side.
- **Capacity planning past ~10k req/min** — we have benchmark data and architecture variants worth a 30-minute call.

This whitepaper updates as our installed base grows. If something in your environment isn't covered, write to us; the gap probably belongs in the next version.
