# FinOps KPI Definitions

## Document Information
| Field | Value |
|-------|-------|
| Version | 1.0 |
| Last Updated | 2026-02 |
| Owner | FinOps Team |
| Review Cycle | Monthly |

## Overview

This document defines the Key Performance Indicators (KPIs) for AI Gateway Platform cost management. These metrics enable teams to understand, optimize, and govern LLM spending.

---

## 1. Cost Efficiency KPIs

### 1.1 Cost Per Request (CPR)

**Definition**: Average cost incurred per API request to the gateway.

```
CPR = Total Spend / Total Requests
```

**Prometheus Query**:
```promql
sum(increase(litellm_spend_total[24h])) / sum(increase(litellm_requests_total[24h]))
```

| Target | Good | Warning | Critical |
|--------|------|---------|----------|
| < $0.01 | < $0.005 | $0.01-0.05 | > $0.05 |

**Use Cases**:
- Identify expensive usage patterns
- Compare efficiency across teams
- Track optimization improvements

---

### 1.2 Cost Per 1K Tokens (CPT)

**Definition**: Average cost per 1,000 tokens processed (input + output combined).

```
CPT = Total Spend / (Total Tokens / 1000)
```

**Prometheus Query**:
```promql
sum(increase(litellm_spend_total[24h])) / (sum(increase(litellm_tokens_total[24h])) / 1000)
```

| Model Tier | Expected CPT |
|------------|--------------|
| Budget (Haiku, GPT-4o-mini) | $0.0002 - $0.001 |
| Standard (Sonnet, GPT-4o) | $0.002 - $0.01 |
| Premium (Opus, GPT-4-turbo) | $0.01 - $0.03 |
| Self-hosted (Llama) | $0.00005 - $0.0003 |

**Use Cases**:
- Model cost comparison
- Vendor negotiation benchmarks
- Self-hosted vs API cost analysis

---

### 1.3 Output/Input Token Ratio

**Definition**: Ratio of output tokens to input tokens, indicating response verbosity.

```
Token Ratio = Output Tokens / Input Tokens
```

**Prometheus Query**:
```promql
sum(increase(litellm_tokens_total{type="output"}[24h]))
/ sum(increase(litellm_tokens_total{type="input"}[24h]))
```

| Use Case | Expected Ratio |
|----------|----------------|
| Chat/Q&A | 0.5 - 2.0 |
| Code Generation | 2.0 - 5.0 |
| Summarization | 0.1 - 0.3 |
| Translation | 0.8 - 1.2 |

**Use Cases**:
- Identify verbose prompts/responses
- Optimize prompt engineering
- Detect potential misuse

---

### 1.4 Cache Hit Rate

**Definition**: Percentage of requests served from cache vs. calling the LLM provider.

```
Cache Hit Rate = Cached Requests / Total Requests × 100%
```

**Prometheus Query**:
```promql
sum(rate(litellm_cache_hits_total[1h])) / sum(rate(litellm_requests_total[1h]))
```

| Target | Good | Needs Improvement |
|--------|------|-------------------|
| > 20% | > 30% | < 10% |

**Use Cases**:
- Validate caching effectiveness
- Identify cacheable workloads
- Reduce redundant API calls

---

## 2. Budget Management KPIs

### 2.1 Budget Utilization Rate

**Definition**: Percentage of allocated budget consumed within the period.

```
Budget Utilization = Current Spend / Budget Limit × 100%
```

**Prometheus Query**:
```promql
# By team
sum(litellm_team_spend_total) by (team) / sum(litellm_team_budget_total) by (team)

# Global
sum(litellm_spend_total) / sum(litellm_global_budget_total)
```

| Status | Utilization |
|--------|-------------|
| 🟢 Healthy | < 70% |
| 🟡 Warning | 70-90% |
| 🔴 Critical | > 90% |

**Alerting Thresholds**:
- Warning at 80%
- Critical at 95%

---

### 2.2 Budget Burn Rate

**Definition**: Rate at which budget is being consumed, used to project exhaustion date.

```
Burn Rate = Current Period Spend / Days Elapsed
Projected Exhaustion = Budget Remaining / Burn Rate
```

**Prometheus Query**:
```promql
# Daily burn rate
sum(increase(litellm_spend_total[24h]))

# Days until budget exhaustion
(sum(litellm_team_budget_total) - sum(litellm_team_spend_total))
/ sum(increase(litellm_spend_total[24h]))
```

| Projection | Action |
|------------|--------|
| > 30 days remaining | Normal |
| 15-30 days | Review usage |
| < 15 days | Urgent optimization needed |

---

### 2.3 Budget Variance

**Definition**: Difference between planned (forecasted) and actual spend.

```
Variance = (Actual Spend - Forecasted Spend) / Forecasted Spend × 100%
```

| Variance | Assessment |
|----------|------------|
| ±10% | On track |
| +10-25% | Over budget |
| +25%+ | Significant overrun |
| -25%+ | Under-utilized |

**Use Cases**:
- Monthly/quarterly financial reporting
- Forecast accuracy improvement
- Resource allocation decisions

---

## 3. Usage Distribution KPIs

### 3.1 Model Mix Distribution

**Definition**: Percentage breakdown of requests/spend by model.

**Prometheus Query**:
```promql
# Spend distribution
sum(increase(litellm_spend_total[24h])) by (model)
/ sum(increase(litellm_spend_total[24h]))

# Request distribution
sum(increase(litellm_requests_total[24h])) by (model)
/ sum(increase(litellm_requests_total[24h]))
```

**Healthy Distribution Example**:
| Model Tier | Request % | Spend % |
|------------|-----------|---------|
| Budget | 60-70% | 10-20% |
| Standard | 25-35% | 40-50% |
| Premium | 5-10% | 30-40% |

---

### 3.2 Team Cost Allocation

**Definition**: Cost distribution across teams/departments.

**Prometheus Query**:
```promql
sum(increase(litellm_spend_total[30d])) by (team)
```

**Reporting Format**:
| Team | Monthly Spend | % of Total | Budget | Utilization |
|------|---------------|------------|--------|-------------|
| Engineering | $X,XXX | XX% | $X,XXX | XX% |
| Data Science | $X,XXX | XX% | $X,XXX | XX% |
| Product | $X,XXX | XX% | $X,XXX | XX% |

---

### 3.3 Provider Distribution

**Definition**: Spend breakdown by LLM provider (OpenAI, Anthropic, XAI, Self-hosted).

**Prometheus Query**:
```promql
sum(increase(litellm_spend_total[24h])) by (provider)
/ sum(increase(litellm_spend_total[24h]))
```

**Strategic Targets**:
| Provider | Target % | Rationale |
|----------|----------|-----------|
| Self-hosted | 40-60% | Cost control, data privacy |
| OpenAI | 20-30% | Specific capabilities |
| Anthropic | 15-25% | Quality, safety |
| XAI | 5-10% | Diversity, fallback |

---

## 4. Operational Efficiency KPIs

### 4.1 Request Success Rate

**Definition**: Percentage of requests that complete successfully (non-error).

```
Success Rate = Successful Requests / Total Requests × 100%
```

**Prometheus Query**:
```promql
sum(rate(litellm_requests_total{status="success"}[5m]))
/ sum(rate(litellm_requests_total[5m]))
```

| SLO Target | Acceptable | Degraded |
|------------|------------|----------|
| 99.9% | > 99.5% | < 99% |

---

### 4.2 Retry Rate

**Definition**: Percentage of requests that required retries.

**Prometheus Query**:
```promql
sum(rate(litellm_retries_total[1h])) / sum(rate(litellm_requests_total[1h]))
```

| Status | Retry Rate |
|--------|------------|
| 🟢 Healthy | < 5% |
| 🟡 Elevated | 5-15% |
| 🔴 High | > 15% |

**Cost Impact**: Each retry adds ~100% cost for that request.

---

### 4.3 Fallback Rate

**Definition**: Percentage of requests routed to fallback models.

**Prometheus Query**:
```promql
sum(rate(litellm_fallback_requests_total[1h])) / sum(rate(litellm_requests_total[1h]))
```

| Healthy | Warning |
|---------|---------|
| < 2% | > 5% |

**Use Cases**:
- Provider reliability assessment
- Capacity planning
- Cost impact analysis (fallbacks may cost more/less)

---

## 5. Unit Economics KPIs

### 5.1 Cost Per User

**Definition**: Average cost per active user per period.

```
Cost Per User = Total Spend / Active Users
```

**Prometheus Query**:
```promql
sum(increase(litellm_spend_total[30d])) / count(count by (user) (litellm_requests_total))
```

**Benchmarks by User Type**:
| User Type | Monthly Cost |
|-----------|--------------|
| Light (< 100 req/day) | $5-20 |
| Moderate (100-1000 req/day) | $20-100 |
| Heavy (> 1000 req/day) | $100-500 |
| Power (automated/batch) | $500+ |

---

### 5.2 Self-Hosted Cost Ratio

**Definition**: Cost savings achieved by using self-hosted models vs. equivalent API calls.

```
Savings Ratio = 1 - (Self-hosted Cost / Equivalent API Cost)
```

**Calculation Components**:
- Infrastructure cost (GPU, compute, storage)
- Operational cost (team time, maintenance)
- Equivalent API cost at same token volume

**Target**: > 50% savings at scale

---

### 5.3 Cost Per Business Outcome

**Definition**: Cost attributed to specific business outcomes (varies by use case).

| Use Case | Metric | Target CPO |
|----------|--------|------------|
| Customer Support | Cost per ticket resolved | < $0.50 |
| Code Generation | Cost per PR assisted | < $2.00 |
| Content Creation | Cost per article | < $1.00 |
| Data Analysis | Cost per report | < $5.00 |

---

## 6. Reporting Schedule

### 6.1 Real-time Dashboard
- All KPIs updated every 30 seconds
- Alert thresholds monitored continuously

### 6.2 Daily Report
- Cost Per Request trend
- Budget utilization by team
- Anomaly highlights
- Delivery: Slack #finops-daily at 9 AM IST

### 6.3 Weekly Report
- Week-over-week cost comparison
- Model mix analysis
- Top 10 spenders
- Optimization recommendations
- Delivery: Email to stakeholders, Monday 10 AM IST

### 6.4 Monthly Report
- Budget variance analysis
- Provider distribution trends
- Unit economics deep dive
- Forecast vs actual
- Chargeback data for finance
- Delivery: Confluence + email, 3rd business day

---

## 7. Grafana Dashboard Panels

### Recommended Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          AI Gateway FinOps Dashboard                         │
├─────────────┬─────────────┬─────────────┬─────────────┬─────────────────────┤
│ Total Spend │ Cost/Request│ Budget Used │ Cache Hit % │    Burn Rate        │
│   (24h)     │    (avg)    │   (month)   │             │  (days remaining)   │
├─────────────┴─────────────┴─────────────┴─────────────┴─────────────────────┤
│                        Hourly Spend by Model (stacked bar)                  │
├─────────────────────────────────────────┬───────────────────────────────────┤
│      Cost Distribution by Team (pie)    │   Budget Utilization (gauges)    │
├─────────────────────────────────────────┼───────────────────────────────────┤
│   Provider Spend Breakdown (pie)        │   Cost Per 1K Tokens (line)      │
├─────────────────────────────────────────┴───────────────────────────────────┤
│                      Token Usage: Input vs Output (timeseries)              │
├─────────────────────────────────────────────────────────────────────────────┤
│                          Top 10 Spenders Table                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Optimization Recommendations

### Based on KPI Analysis

| KPI Signal | Recommendation |
|------------|----------------|
| High CPR | Review prompt length, enable caching |
| Low cache hit rate | Identify repeated queries, tune TTL |
| High token ratio | Optimize prompts, set max_tokens |
| Budget > 80% | Alert team, review heavy users |
| High retry rate | Check provider health, adjust timeouts |
| Premium model > 30% spend | Evaluate if premium needed, try cheaper alternatives |
| Self-hosted < 40% | Migrate suitable workloads to vLLM |

---

## Appendix A: Prometheus Recording Rules

```yaml
groups:
  - name: finops-recording-rules
    interval: 1m
    rules:
      - record: aigateway:cost_per_request:1h
        expr: sum(increase(litellm_spend_total[1h])) / sum(increase(litellm_requests_total[1h]))

      - record: aigateway:cost_per_1k_tokens:1h
        expr: sum(increase(litellm_spend_total[1h])) / (sum(increase(litellm_tokens_total[1h])) / 1000)

      - record: aigateway:budget_utilization:team
        expr: sum(litellm_team_spend_total) by (team) / sum(litellm_team_budget_total) by (team)

      - record: aigateway:daily_spend:model
        expr: sum(increase(litellm_spend_total[24h])) by (model)

      - record: aigateway:cache_hit_rate:1h
        expr: sum(rate(litellm_cache_hits_total[1h])) / sum(rate(litellm_requests_total[1h]))

      - record: aigateway:token_ratio:1h
        expr: sum(rate(litellm_tokens_total{type="output"}[1h])) / sum(rate(litellm_tokens_total{type="input"}[1h]))
```

---

## Appendix B: SQL Queries for FinOps Reporter

```sql
-- Daily cost by team
SELECT
    date,
    team_id,
    SUM(total_cost) as daily_cost,
    SUM(request_count) as requests,
    SUM(total_cost) / NULLIF(SUM(request_count), 0) as cost_per_request
FROM cost_tracking_daily
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY date, team_id
ORDER BY date DESC, daily_cost DESC;

-- Model efficiency comparison
SELECT
    model,
    SUM(total_cost) as total_cost,
    SUM(input_tokens + output_tokens) as total_tokens,
    SUM(total_cost) / NULLIF(SUM(input_tokens + output_tokens), 0) * 1000 as cost_per_1k_tokens
FROM cost_tracking_daily
WHERE date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY model
ORDER BY cost_per_1k_tokens;

-- Budget burn rate projection
WITH daily_spend AS (
    SELECT
        team_id,
        AVG(total_cost) as avg_daily_spend
    FROM cost_tracking_daily
    WHERE date >= CURRENT_DATE - INTERVAL '7 days'
    GROUP BY team_id
)
SELECT
    team_id,
    avg_daily_spend,
    budget_limit,
    (budget_limit - current_spend) / NULLIF(avg_daily_spend, 0) as days_remaining
FROM daily_spend
JOIN team_budgets USING (team_id);
```
