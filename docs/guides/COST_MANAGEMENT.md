# Cost Management Guide

The AI Gateway tracks every token and dollar spent across all providers, enforces budgets at multiple levels, and provides reporting tools to optimize your AI spend.

## How Cost Tracking Works

Every request that passes through the gateway is logged with:

- **Model used** (including fallback resolution)
- **Input tokens** and **output tokens** consumed
- **Computed cost** based on the model's per-token pricing
- **User ID** and **team ID** of the requester
- **Timestamp** for time-based aggregation

Costs are calculated using each model's configured pricing (stored in the `model_routing_config` database table) and recorded in LiteLLM's native `LiteLLM_SpendLogs` table. Daily aggregates are stored in the `cost_tracking_daily` table for efficient reporting.

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

## FinOps Reporter

The FinOps Reporter service (port 8082) provides detailed cost analytics endpoints. Enable it with the `finops` profile:

```bash
docker compose --env-file config/.env --profile finops up -d
```

### Available Endpoints

| Endpoint                          | Method | Description                              |
|-----------------------------------|--------|------------------------------------------|
| `/reports/cost`                   | GET    | Cost report by period (daily/weekly/monthly/custom) |
| `/reports/trend`                  | GET    | Cost trend analysis over time            |
| `/reports/budget-utilization`     | GET    | Budget utilization status                |
| `/reports/export`                 | GET    | Export cost data as CSV or JSON          |
| `/reports/summary`               | GET    | Dashboard summary statistics             |

### Cost Report

```bash
# Daily cost report
curl "http://localhost:8082/reports/cost?period=daily"

# Monthly cost report for a specific team
curl "http://localhost:8082/reports/cost?period=monthly&team_id=engineering"

# Custom date range
curl "http://localhost:8082/reports/cost?period=custom&start_date=2026-01-01&end_date=2026-01-31"
```

The response includes breakdowns by model, user, and team:

```json
{
  "period": "monthly",
  "start_date": "2026-02-01",
  "end_date": "2026-02-16",
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
curl "http://localhost:8082/reports/trend?days=30"

# Cost trend for a specific model
curl "http://localhost:8082/reports/trend?days=30&model=claude-sonnet-4.5"
```

The response includes a trend direction (`increasing`, `decreasing`, or `stable`) and percentage change.

### Exporting Data

```bash
# Export as CSV
curl "http://localhost:8082/reports/export?format=csv&period=monthly" -o cost_report.csv

# Export as JSON
curl "http://localhost:8082/reports/export?format=json&period=monthly" -o cost_report.json
```

### Dashboard Summary

```bash
curl http://localhost:8082/reports/summary
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

The semantic cache (port 8083, `experimental` profile) caches responses for semantically similar prompts. If a new prompt is 92%+ similar to a cached one, the cached response is returned instantly at zero cost.

```bash
docker compose --env-file config/.env --profile experimental up -d
```

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

Check the FinOps Reporter trend endpoint weekly. If costs are trending upward, drill into the model and user breakdowns to find the source.

### 6. Set Per-Team Budgets

Give each team its own budget with appropriate limits. This creates accountability and prevents a single team's spike from affecting the whole organization.

### 7. Consider Self-Hosted Models

For high-volume, latency-insensitive workloads, route to self-hosted models (Ollama, local GPU) to eliminate per-token costs entirely. Add the `local-models` profile:

```bash
docker compose --env-file config/.env --profile local-models up -d
```

Then use the `local` provider alias or specific model names like `llama-3.1-70b`.
