# Observability Guide

Monitor, trace, and analyze your AI Control Plane with Prometheus, Grafana, Jaeger, and OpenTelemetry.

## Enabling Observability

Start the observability stack alongside the core services:

```bash
docker compose --env-file config/.env --profile observability up -d
```

This adds four services:

| Service | URL | Purpose |
|---------|-----|---------|
| Grafana | [localhost:3030](http://localhost:3030) | Dashboards and visualization |
| Prometheus | [localhost:9090](http://localhost:9090) | Metrics collection and querying |
| Jaeger | [localhost:16686](http://localhost:16686) | Distributed tracing |
| OTEL Collector | localhost:4317 (gRPC), localhost:4318 (HTTP) | Telemetry aggregation hub |

## Architecture

```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│   LiteLLM   │  │  Admin API  │  │  Workflows  │  ... (all services)
│  :4000      │  │  :8086      │  │  :8085      │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │
       │    OTLP gRPC   │                │
       ▼                ▼                ▼
┌──────────────────────────────────────────────┐
│           OTEL Collector (:4317)             │
│  Receives traces, metrics, logs from all     │
│  services via OpenTelemetry protocol         │
└────┬──────────────┬──────────────┬───────────┘
     │              │              │
     ▼              ▼              ▼
┌──────────┐  ┌──────────┐  ┌──────────┐
│Prometheus│  │  Jaeger  │  │  File    │
│  :8889   │  │ :16686   │  │ Exporters│
└────┬─────┘  └──────────┘  └──────────┘
     │
     ▼
┌──────────┐
│ Grafana  │
│  :3030   │
└──────────┘
```

All platform services send telemetry to the OTEL Collector, which routes traces, metrics, and logs to the appropriate backends. Prometheus also scrapes LiteLLM directly for native metrics.

## Grafana Dashboards

Grafana ships with two pre-built dashboards. Log in with username `admin` and password `admin` (configurable via `GRAFANA_ADMIN_PASSWORD` in `config/.env`).

### AI Control Plane Platform Overview

**URL:** `http://localhost:3030/d/ai-gateway-overview`

Real-time operational dashboard powered by Prometheus metrics.

**Row 1 -- Overview Stats:**

| Panel | Metric | Thresholds |
|-------|--------|------------|
| Total Requests | `litellm_requests_metric_total` | -- |
| Error Rate | Failed / total (%) | Yellow > 1%, Red > 5% |
| P95 Latency | `litellm_llm_api_latency_metric_bucket` | Yellow > 5s, Red > 15s |
| Total Spend | `litellm_spend_metric_total` (USD) | -- |
| Total Tokens | `litellm_total_tokens_metric_total` | -- |
| Active Models | Count of distinct model labels | -- |

**Row 2 -- Request & Latency Trends:**
- Request rate by model (requests/second, time series)
- Latency percentiles by model (p50, p95, p99)

**Row 3 -- Cost & Tokens:**
- Hourly spend by model (stacked bar, USD)
- Token rate by model (input/output tokens per minute)

**Row 4 -- Provider Stats:**
- Request distribution pie chart (by model)
- Spend distribution pie chart (by model)
- Failed requests by model (time series)

### FinOps Cost Tracking

**URL:** `http://localhost:3030/d/finops-cost-tracking`

SQL-powered cost analytics dashboard querying LiteLLM's spend logs directly in PostgreSQL.

**Row 1 -- Cost Overview:** Today's spend, this week's spend, total spend, today's requests

**Row 2 -- Token Usage:** Total tokens, input tokens, output tokens, models used

**Row 3 -- Model Breakdown:** Three pie charts showing top 10 models by spend, requests, and tokens

**Row 4 -- Recent Requests:** Table of the last 50 requests with timestamp, model, user, spend, and token breakdown

## Prometheus Metrics

Prometheus scrapes three targets every 15 seconds:

| Target | Endpoint | Metrics |
|--------|----------|---------|
| Prometheus | `localhost:9090` | Self-monitoring |
| OTEL Collector | `otel-collector:8889` | Aggregated metrics from all services |
| LiteLLM | `litellm:4000/metrics/` | Native LLM proxy metrics |

### Key Metrics

**Request metrics:**
- `litellm_requests_metric_total` -- total requests by model, status
- `litellm_llm_api_latency_metric_bucket` -- request latency histogram
- `litellm_llm_api_failed_requests_metric_total` -- failed request count

**Cost metrics:**
- `litellm_spend_metric_total` -- cumulative spend in USD by model
- `litellm_total_tokens_metric_total` -- total tokens consumed

**System metrics (via OTEL host metrics):**
- CPU, memory, disk, and network utilization at 30-second intervals

### Example PromQL Queries

```promql
# Request rate per model (last 5 minutes)
rate(litellm_requests_metric_total[5m])

# P95 latency by model
histogram_quantile(0.95, rate(litellm_llm_api_latency_metric_bucket[5m]))

# Hourly spend by model
increase(litellm_spend_metric_total[1h])

# Error rate percentage
rate(litellm_llm_api_failed_requests_metric_total[5m]) / rate(litellm_requests_metric_total[5m]) * 100
```

## Jaeger Tracing

Jaeger provides distributed tracing across all platform services. Access the UI at **http://localhost:16686**.

### Viewing Traces

1. Open the Jaeger UI.
2. Select a service from the dropdown (e.g., `litellm`, `admin-api`, `semantic-cache`).
3. Click **Find Traces** to see recent requests.
4. Click any trace to see the full span tree -- you can follow a request from the API gateway through caching, routing, and provider calls.

### Trace Attributes

Services emit spans with AI-specific attributes:

| Attribute | Description |
|-----------|-------------|
| `llm.model` | Model requested |
| `llm.provider` | Provider that served the request |
| `ai.cost.input_tokens` | Input token count |
| `ai.cost.output_tokens` | Output token count |
| `cache.hit` | Whether semantic cache was hit |
| `cache.similarity` | Similarity score (if cache checked) |

## OpenTelemetry Collector

The OTEL Collector acts as the central telemetry hub. Configuration is at `config/otel/otel-collector-config.yaml`.

### Pipelines

| Pipeline | Receivers | Processors | Exporters |
|----------|-----------|------------|-----------|
| Traces | OTLP | memory_limiter, filter, attributes, batch | debug, file |
| Metrics | OTLP, Prometheus, host metrics | memory_limiter, resource, batch | Prometheus, debug, file |
| Logs | OTLP | memory_limiter, resource, batch | debug |

### Processors

- **memory_limiter** -- caps memory at 512 MiB to prevent OOM
- **filter/health** -- drops health check spans (`/health`, `/ready`, `/live`) to reduce noise
- **attributes/ai_gateway** -- maps LLM-specific attributes to standardized AI metrics
- **batch** -- groups telemetry with 10s timeout for efficient export

### File Exporters

Traces and metrics are also written to JSON files with 100 MB rotation, 7-day retention, and 3 backup files. These are useful for offline analysis or compliance.

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GRAFANA_PORT` | `3030` | Grafana external port |
| `GRAFANA_ADMIN_PASSWORD` | `admin` | Grafana admin password |
| `PROMETHEUS_PORT` | `9090` | Prometheus external port |
| `JAEGER_PORT` | `16686` | Jaeger UI external port |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://otel-collector:4317` | OTLP endpoint for services |

### Adding Custom Dashboards

Place JSON dashboard files in `kubernetes/base/observability/grafana/dashboards/`. Grafana auto-provisions them on startup.

### Alerting

Grafana supports alert rules on any dashboard panel. Common alerts to configure:

- **Error rate > 5%** -- fires when the proportion of failed requests exceeds threshold
- **P95 latency > 10s** -- fires when response times degrade
- **Daily spend > $X** -- fires when cost exceeds a daily budget

Configure alerts in Grafana UI under **Alerting > Alert Rules**.

## Production Considerations

- Set `GRAFANA_ADMIN_PASSWORD` to a strong value in production
- Use persistent volumes for Prometheus (`prometheus-data`) and Grafana (`grafana-data`) to retain data across restarts
- The OTEL Collector's Jaeger exporter is defined but commented out by default -- uncomment it in `config/otel/otel-collector-config.yaml` to enable direct Jaeger trace export
- Consider increasing Prometheus retention beyond the default 15 days for long-term cost analysis

## Related Guides

- [Cost Management Guide](./cost-management.md) -- budgets, alerts, and FinOps reporting
- [Admin Guide](./admin-guide.md) -- Admin Console walkthrough
- [Quickstart](./quickstart.md) -- get the platform running
