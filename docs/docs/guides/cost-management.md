# Cost Management Guide

The AI Control Plane tracks every token and dollar spent across all providers, enforces budgets at multiple levels, and provides reporting tools to optimize your AI spend.

## How Cost Tracking Works

Every request that passes through the gateway is logged with:

- **Model used** (including fallback resolution)
- **Input tokens** and **output tokens** consumed
- **Computed cost** based on the model's per-token pricing
- **User ID** and **team ID** of the requester
- **Timestamp** for time-based aggregation

Costs are calculated using each model's configured pricing and recorded in LiteLLM's native `LiteLLM_SpendLogs` table. A `cost_tracking_daily` database view provides daily aggregates for reporting.

Cost tracking is enabled by default. You can toggle it off in the Admin UI under **Settings > Features > Cost Tracking**.

## Setting Up Budgets

Budgets define spending limits for users, teams, or the entire platform. When a budget limit is approached or exceeded, the gateway can send alerts and optionally block further requests.

### Budget Concepts

| Term               | Description                                                      |
|--------------------|------------------------------------------------------------------|
| **Monthly limit**  | Maximum dollar amount that can be spent per calendar month       |
| **Soft limit**     | Percentage of the monthly limit that triggers a warning (default: 80%) |
| **Hard limit**     | Percentage of the monthly limit that blocks requests (default: 100%) |
| **Entity type**    | What the budget applies to: `user`, `team`, or `global`         |
| **Entity ID**      | The specific user or team ID (leave blank for global budgets)   |

### Creating Budgets in the Admin UI

1. Open **http://localhost:5173** and log in.
2. Navigate to **Budgets** from the sidebar.
3. Click the **Create Budget** button.
4. Fill in the form:
   - **Name**: A descriptive name (e.g., "Engineering Team Monthly")
   - **Entity Type**: Choose `team`, `user`, or `global`
   - **Entity ID**: The team or user ID this budget applies to
   - **Monthly Limit**: Dollar amount (e.g., 500)
   - **Soft Limit %**: When to send warnings (e.g., 0.8 for 80%)
   - **Hard Limit %**: When to block requests (e.g., 1.0 for 100%)
   - **Alert Email**: Where to send budget notifications
5. Click **Create**.

Each budget appears as a card showing the name, current spend, limit, and a utilization progress bar.

### Creating Budgets via the Admin API

```bash
# First, get a JWT token
TOKEN=$(curl -s http://localhost:8086/auth/login \
  -H "Content-Type: application/json" \
  -d '{"api_key": "$LITELLM_KEY"}' | jq -r '.access_token')

# Create a team budget
curl http://localhost:8086/api/v1/budgets \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "Engineering Team Monthly",
    "entity_type": "team",
    "entity_id": "engineering",
    "monthly_limit": 500.00,
    "soft_limit_percent": 0.8,
    "hard_limit_percent": 1.0,
    "alert_email": "eng-leads@company.com"
  }'

# Create a global budget
curl http://localhost:8086/api/v1/budgets \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "Platform Monthly Cap",
    "entity_type": "global",
    "monthly_limit": 5000.00,
    "soft_limit_percent": 0.75,
    "hard_limit_percent": 0.95,
    "alert_email": "platform-ops@company.com"
  }'
```

### Updating a Budget

```bash
curl -X PUT http://localhost:8086/api/v1/budgets/{budget_id} \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "monthly_limit": 750.00,
    "soft_limit_percent": 0.7
  }'
```

### Listing All Budgets

```bash
curl http://localhost:8086/api/v1/budgets \
  -H "Authorization: Bearer $TOKEN"
```

## Soft Limits vs. Hard Limits

**Soft limit** (default: 80% of monthly limit):
- Triggers an alert notification to the configured email address.
- Requests continue to be served normally.
- Shows a yellow warning indicator on the budget card in the Admin UI.
- Purpose: give the team lead or finance admin time to react before hitting the cap.

**Hard limit** (default: 100% of monthly limit):
- Triggers a critical alert notification.
- When budget enforcement is enabled, requests from the affected entity are blocked with a 429 status.
- Shows a red indicator on the budget card in the Admin UI.
- Purpose: prevent uncontrolled overspend.

Budget enforcement can be toggled globally in **Settings > Features > Budget Enforcement**.

### Pre-configured Global Budget

The platform ships with a default global budget in `config/litellm/config.yaml`:

```
Soft budget:  $1,000/month (warning)
Hard budget:  $1,500/month (blocking)
Per-key default: $100/month, 100 RPM, 100,000 TPM
```

Adjust these values in the config file or override them per team/user through the Admin UI.

## Cost Predictor

The Cost Predictor service (port 8080) estimates the cost of an LLM request **before** execution. Enable it with the `finops` profile:

```bash
docker compose --env-file config/.env --profile finops up -d
```

### Predicting Request Cost

```bash
curl -X POST http://localhost:8080/predict \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4.5",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Explain quantum computing in one paragraph."}
    ],
    "max_tokens": 500
  }'
```

Response:
```json
{
  "model": "claude-sonnet-4.5",
  "input_tokens": 28,
  "estimated_output_tokens": 275,
  "input_cost_usd": 0.000084,
  "estimated_output_cost_usd": 0.004125,
  "total_estimated_cost_usd": 0.004209,
  "budget_remaining_usd": 95.42,
  "within_budget": true,
  "warning": null
}
```

Pass an `X-Api-Key` header to also check against the key's budget:

```bash
curl -X POST http://localhost:8080/predict \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $API_KEY" \
  -d '{"model": "gpt-5", "messages": [{"role": "user", "content": "Hello"}]}'
```

### Output Token Estimation

The predictor uses model-specific verbosity profiles to estimate output tokens:

| Model Type | Utilization of max_tokens | Output/Input Ratio |
|------------|--------------------------|-------------------|
| Reasoning (o3, o3-pro) | 85-90% | 4-5x |
| Powerful (opus, gpt-5.2) | 65-70% | 2.5-3x |
| Standard (sonnet, gpt-5) | 55% | 2x |
| Fast (mini, haiku) | 35-40% | 1.2-1.5x |

### Budget Validation

```bash
curl -X POST http://localhost:8080/budget/check \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "$API_KEY",
    "estimated_cost": 0.05
  }'
```

Response:
```json
{
  "allowed": true,
  "budget_limit": 100.0,
  "current_spend": 42.58,
  "remaining": 57.42,
  "message": null
}
```

### Model Pricing

```bash
# Get all model pricing (cost per 1M tokens) — auto-updated from litellm
curl http://localhost:8080/pricing
```

### Cost Predictor Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/predict` | Predict cost of a request (with optional budget check) |
| POST | `/budget/check` | Check if a cost fits within a key's budget |
| GET | `/pricing` | Get all model pricing (litellm auto-updated + self-hosted) |
| GET | `/health` | Health check |

## Budget Webhook

The Budget Webhook service (port 8081) acts as a LiteLLM webhook that enforces budget limits on every request. It runs as part of the `finops` profile.

### How It Works

LiteLLM calls the webhook before each request:

- **Pre-request** (`/webhook/pre-request`): Checks the API key's budget, predicts the request cost, and blocks the request if it would exceed the hard limit.

Actual costs are recorded automatically by LiteLLM in the `LiteLLM_SpendLogs` table.

### Enforcement Flow

```
Request arrives → Pre-request webhook
                       │
              ┌────────┴────────┐
              │                 │
         Usage < 80%      80% ≤ Usage < 100%      Usage ≥ 100%
         (Allow)          (Allow + Warning)        (Block 429)
              │                 │                       │
              ▼                 ▼                       ▼
         Process request   Process request         Reject request
                                                   + Send alert
```

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SOFT_LIMIT_THRESHOLD` | `0.8` | Percentage at which warnings are sent (80%) |
| `HARD_LIMIT_THRESHOLD` | `1.0` | Percentage at which requests are blocked (100%) |
| `ALERT_WEBHOOK_URL` | (none) | External webhook URL for alert notifications |
| `COST_PREDICTOR_URL` | `http://localhost:8080` | Cost predictor service URL |

### Budget Alert Types

| Alert Type | Trigger | Action |
|------------|---------|--------|
| `approaching_limit` | Spend ≥ soft limit | Allow request, send notification |
| `request_exceeds_budget` | Estimated cost > remaining budget | Block request |
| `budget_exceeded` | Spend ≥ hard limit | Block request, send notification |

### Viewing Alerts

```bash
# Get recent alerts
curl http://localhost:8081/alerts

# Filter by team
curl "http://localhost:8081/alerts?team_id=engineering"

# Filter by user
curl "http://localhost:8081/alerts?user_id=user-123"
```

### Budget Webhook Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/webhook/pre-request` | Pre-request budget validation (called by LiteLLM) |
| GET | `/alerts` | List recent budget alerts |
| GET | `/health` | Health check |

## FinOps Reports (Admin API)

Cost reports are available through the Admin API (port 8086). These query LiteLLM's native `LiteLLM_SpendLogs` table directly — no separate service needed.

### Available Endpoints

| Endpoint                              | Method | Description                              |
|---------------------------------------|--------|------------------------------------------|
| `/api/v1/reports/cost`                | GET    | Cost report by period (daily/weekly/monthly/custom) |
| `/api/v1/reports/trend`               | GET    | Cost trend analysis over time            |
| `/api/v1/reports/export`              | GET    | Export cost data as CSV or JSON          |
| `/api/v1/reports/summary`             | GET    | Dashboard summary statistics             |

All report endpoints require JWT authentication (same as other Admin API endpoints).

### Cost Report

```bash
# Daily cost report
curl "http://localhost:8086/api/v1/reports/cost?period=daily" -H "Authorization: Bearer $TOKEN"

# Monthly cost report for a specific team
curl "http://localhost:8086/api/v1/reports/cost?period=monthly&team_id=engineering" -H "Authorization: Bearer $TOKEN"

# Custom date range
curl "http://localhost:8086/api/v1/reports/cost?period=custom&start_date=2026-01-01&end_date=2026-01-31" -H "Authorization: Bearer $TOKEN"
```

The response includes breakdowns by model, user, and team:

```json
{
  "period": "monthly",
  "start_date": "2026-02-01",
  "end_date": "2026-02-17",
  "total_cost": 1247.53,
  "total_requests": 45230,
  "total_input_tokens": 12500000,
  "total_output_tokens": 8700000,
  "breakdown_by_model": [...],
  "breakdown_by_user": [...],
  "breakdown_by_team": [...]
}
```

### Cost Trend Analysis

```bash
# 30-day cost trend
curl "http://localhost:8086/api/v1/reports/trend?days=30" -H "Authorization: Bearer $TOKEN"

# Cost trend for a specific model
curl "http://localhost:8086/api/v1/reports/trend?days=30&model=claude-sonnet-4.5" -H "Authorization: Bearer $TOKEN"
```

The response includes a trend direction (`increasing`, `decreasing`, or `stable`) and percentage change.

### Exporting Data

```bash
# Export as CSV
curl "http://localhost:8086/api/v1/reports/export?format=csv&period=monthly" -H "Authorization: Bearer $TOKEN" -o cost_report.csv

# Export as JSON
curl "http://localhost:8086/api/v1/reports/export?format=json&period=monthly" -H "Authorization: Bearer $TOKEN" -o cost_report.json
```

### Dashboard Summary

```bash
curl "http://localhost:8086/api/v1/reports/summary" -H "Authorization: Bearer $TOKEN"
```

Returns today's cost, this week's cost, this month's cost, and top 5 models by spend.

## Budget Alerts

When a budget crosses its soft or hard limit threshold, the system generates an alert. Alerts are sent to the email address configured on the budget.

Alert types:

| Alert Level | Trigger                    | Action                              |
|-------------|---------------------------|-------------------------------------|
| Warning     | Spend reaches soft limit % | Email notification sent             |
| Critical    | Spend reaches hard limit % | Email notification + request blocking (if enforcement is on) |

To receive alerts, ensure the `alert_email` field is set when creating budgets. The Budget Webhook service (port 8081, part of the `finops` profile) processes these alerts.

## Chargeback & Cost Allocation

The chargeback system maps AI spending to business cost centers, enabling finance teams to allocate costs accurately.

### Cost Allocation Rules

Allocation rules map teams to cost centers, projects, or departments. Each rule specifies an allocation percentage (defaulting to 100%).

#### Creating Rules in the Admin UI

1. Navigate to **Chargeback** from the sidebar.
2. On the **Allocation Rules** tab, click **Create Rule**.
3. Fill in:
   - **Name**: Descriptive name (e.g., "Engineering to CC-1234")
   - **Team**: The team whose spend is being allocated
   - **Allocation Type**: `cost_center`, `project`, or `department`
   - **Allocation Target**: The target identifier (e.g., CC-1234, PROJ-AI-001)
   - **Allocation Percent**: Percentage of the team's spend to allocate (default: 100%)
   - **Metadata**: Optional JSON with SAP codes, Workday IDs, GL accounts
4. Click **Create**.

#### Creating Rules via API

```bash
curl -X POST http://localhost:8086/api/v1/cost-allocation/rules \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Engineering to CC-1234",
    "team_id": "engineering-team-uuid",
    "allocation_type": "cost_center",
    "allocation_target": "CC-1234",
    "allocation_percent": 100.0,
    "metadata": {"gl_account": "6200-AI-SERVICES"}
  }'
```

### Chargeback Reports

Reports aggregate spend by period and apply allocation rules to produce a cost breakdown.

1. Navigate to **Chargeback > Reports** tab.
2. Click **Generate Report** and select the period (e.g., 2026-02).
3. The report shows total cost, breakdown by team and allocation target.
4. Reports go through a lifecycle: `draft` → `finalized` → `exported`.
5. Click **Export** to download as CSV, JSON, or SAP format.

#### Generating Reports via API

```bash
# Generate a report
curl -X POST http://localhost:8086/api/v1/chargeback/reports/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"period": "2026-02"}'

# Export a report
curl "http://localhost:8086/api/v1/chargeback/reports/{report_id}/export?format=csv" \
  -H "Authorization: Bearer $TOKEN" -o chargeback_feb.csv
```

### Budget Forecasts

The platform generates spending forecasts using a weighted moving average over the last 3 months.

```bash
# Get forecasts
curl http://localhost:8086/api/v1/reports/forecast \
  -H "Authorization: Bearer $TOKEN"

# Generate a new forecast
curl -X POST http://localhost:8086/api/v1/reports/forecast/generate \
  -H "Authorization: Bearer $TOKEN"
```

Forecasts include `forecasted_cost`, `confidence_low`, and `confidence_high` for each team. View them in the Admin UI under **Chargeback > Forecasts** tab.

## SLA Monitoring

The SLA monitoring system tracks provider health metrics and alerts when service level agreements are violated.

### SLA Definitions

Define target metrics for each provider or model:

| Metric | Description |
|--------|-------------|
| Target P50 latency | Median response time target (ms) |
| Target P95 latency | 95th percentile response time target (ms) |
| Target P99 latency | 99th percentile response time target (ms) |
| Target error rate | Maximum acceptable error rate (e.g., 0.01 = 1%) |
| Target availability | Minimum uptime (e.g., 0.999 = 99.9%) |

#### Creating SLA Definitions

1. Navigate to **SLA Monitor** from the sidebar.
2. Click **Create Definition**.
3. Set the provider, model pattern, and target metrics.
4. Configure alert channels and evaluation window.

#### Via API

```bash
curl -X POST http://localhost:8086/api/v1/sla/definitions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "OpenAI GPT-4o SLA",
    "provider": "openai",
    "model_pattern": "gpt-4o*",
    "target_p95_ms": 3000,
    "target_error_rate": 0.01,
    "target_availability": 0.999,
    "evaluation_window_minutes": 60
  }'
```

### Provider Health

The background health collector runs every 5 minutes, querying LiteLLM spend logs to compute per-provider metrics. View the results:

```bash
# Current health
curl http://localhost:8086/api/v1/sla/health \
  -H "Authorization: Bearer $TOKEN"

# Historical metrics (for charts)
curl "http://localhost:8086/api/v1/sla/health/history?hours=24" \
  -H "Authorization: Bearer $TOKEN"
```

### SLA Violations

When metrics breach SLA thresholds, violations are recorded and alerts are sent to configured channels.

```bash
# List active violations
curl http://localhost:8086/api/v1/sla/violations/active \
  -H "Authorization: Bearer $TOKEN"

# Resolve a violation
curl -X POST http://localhost:8086/api/v1/sla/violations/{id}/resolve \
  -H "Authorization: Bearer $TOKEN"
```

### Failover Rules

Failover rules automatically route traffic away from degraded providers:

```bash
curl -X POST http://localhost:8086/api/v1/sla/failover-rules \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "primary_model": "gpt-4o",
    "fallback_model": "claude-sonnet-4.5",
    "trigger_condition": "error_rate",
    "trigger_threshold": 0.05,
    "cooldown_minutes": 15
  }'
```

## Cost Optimization Tips

### 1. Use Model Aliases

Route requests through capability aliases like `fast` or `cost-effective` instead of pinning to expensive models. The gateway selects the most economical available option:

```python
# Instead of always using the most expensive model...
response = client.chat.completions.create(model="gpt-5", ...)

# ...use the cost-effective alias for tasks that don't need premium quality
response = client.chat.completions.create(model="cost-effective", ...)
```

### 2. Enable Semantic Caching

LiteLLM supports semantic caching via Redis. When enabled, semantically similar prompts return cached responses instantly at zero cost. Configure caching in the Admin UI under **Settings > Caching**.

### 3. Set max_tokens

Always set `max_tokens` to the minimum needed for your use case. Output tokens are typically 3-4x more expensive than input tokens:

```python
response = client.chat.completions.create(
    model="claude-sonnet-4.5",
    messages=[{"role": "user", "content": "Is this email spam? Answer yes or no."}],
    max_tokens=10,  # Short answer tasks don't need 4096 tokens
)
```

### 4. Use Tiered Models

Match model power to task complexity:

| Task Type            | Recommended Alias | Example Models                          |
|----------------------|-------------------|-----------------------------------------|
| Classification       | `fast`            | gpt-5-mini, claude-haiku-4.5           |
| Summarization        | `smart`           | claude-sonnet-4.5, gpt-5              |
| Complex analysis     | `powerful`        | claude-opus-4.5, gpt-5.2              |
| Math/Logic           | `reasoning`       | o3, deepseek-r1                        |
| Routine code         | `coding`          | deepseek-coder, claude-sonnet-4.5      |

### 5. Monitor and Act on Trends

Check the Admin API trend endpoint (`/api/v1/reports/trend`) weekly. If costs are trending upward, drill into the model and user breakdowns to find the source.

### 6. Set Per-Team Budgets

Give each team its own budget with appropriate limits. This creates accountability and prevents a single team's spike from affecting the whole organization.

### 7. Consider Self-Hosted Models

For high-volume, latency-insensitive workloads, route to self-hosted models (Ollama, local GPU) to eliminate per-token costs entirely. Add the `local-models` profile:

```bash
docker compose --env-file config/.env --profile local-models up -d
```

Then use the `local` provider alias or specific model names like `llama-3.1-70b`.

## Related Guides

- [Admin Guide - Chargeback](./admin-guide.md#chargeback) -- detailed UI walkthrough
- [Admin Guide - SLA Monitor](./admin-guide.md#sla-monitor) -- provider health dashboard
- Hello World Examples -- see `examples/hello-world/` in the repository for cost tracking scripts
