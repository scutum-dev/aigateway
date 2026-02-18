# AI Control Plane Demo Runbook

## Quick Status Check

```bash
# Check all services
docker compose ps

# Expected: 23 services (with --profile full), all healthy
```

## Service Endpoints

| Service | URL | Credentials |
|---------|-----|-------------|
| Landing Page | http://localhost:9999 | - |
| **Admin UI** | http://localhost:5173 | API Key: `$LITELLM_KEY` |
| Admin API (Swagger) | http://localhost:8086/docs | - |
| LiteLLM API | http://localhost:4000 | `$LITELLM_KEY` |
| LiteLLM UI | http://localhost:4000/ui | `$LITELLM_KEY` |
| Playground | http://localhost:6001 | - |
| Deck | http://localhost:6002 | - |
| Docs Site | http://localhost:8089 | - |
| Agent Gateway | http://localhost:9000 | - |
| **Grafana** | http://localhost:3030 | admin / admin@123 |
| Prometheus | http://localhost:9090 | - |
| Jaeger | http://localhost:16686 | - |
| Vault | http://localhost:8200 | Token: `root-token-for-dev` |
| Temporal UI | http://localhost:8088 | - |
| Cost Predictor | http://localhost:8080 | - |
| Budget Webhook | http://localhost:8081 | - |
| Workflow Engine | http://localhost:8085 | - |

---

## Admin UI Features (http://localhost:5173)

**Login:** Use API key `$LITELLM_KEY`

### What you can do:

| Feature | Description |
|---------|-------------|
| **Dashboard** | Real-time metrics, cost charts, provider health |
| **Models** | View/configure model routing, access tiers, deprecation badges |
| **API Keys** | Generate and manage keys with budgets and model restrictions |
| **Teams** | Manage teams, members, and content policies |
| **Budgets** | Set spending limits per user/team/global |
| **Organizations** | Org hierarchy, business units, SSO/OIDC config, members |
| **Audit Log** | Filterable trail of every config change with export |
| **Prompts** | Versioned prompt templates with approval workflows |
| **Rate Limits** | Granular rate limiting per user/team/model |
| **Model Access** | Access tiers (standard/premium/experimental) with approvals |
| **Chargeback** | Cost allocation rules, reports, budget forecasts |
| **SLA Monitor** | Provider health, latency tracking, SLA violations, failover |
| **A/B Tests** | Model comparison with traffic splitting and metrics |
| **Events** | Event subscriptions (Slack, PagerDuty, email, webhooks) |
| **MCP Servers** | Configure MCP tool servers with deploy-to-gateway |
| **A2A Agents** | Agent-to-Agent protocol management |
| **Guardrails** | Content filtering, DLP detectors, safety rules |
| **Workflows** | LangGraph workflow templates and execution history |
| **Settings** | Platform-wide toggles, caching, maintenance mode |

### Admin API Endpoints (http://localhost:8086/docs)

```
POST   /auth/login                          - Login with API key
GET    /auth/me                             - Get current user info
GET    /api/v1/models                       - List models
PUT    /api/v1/models/{id}                  - Update model config
GET    /api/v1/teams                        - List teams
POST   /api/v1/teams                        - Create team
GET    /api/v1/budgets                      - List budgets
POST   /api/v1/budgets                      - Create budget
GET    /api/v1/organizations                - List organizations
POST   /api/v1/organizations                - Create organization
GET    /api/v1/audit-logs                   - List audit events
GET    /api/v1/prompts                      - List prompt templates
POST   /api/v1/prompts                      - Create prompt template
GET    /api/v1/rate-limits                  - List rate limit policies
POST   /api/v1/rate-limits                  - Create rate limit policy
GET    /api/v1/model-access/tiers           - List access tiers
POST   /api/v1/model-access/requests        - Submit access request
GET    /api/v1/cost-allocation/rules        - List allocation rules
POST   /api/v1/chargeback/reports/generate  - Generate chargeback report
GET    /api/v1/sla/definitions              - List SLA definitions
GET    /api/v1/sla/health                   - Provider health status
GET    /api/v1/sla/violations               - List SLA violations
GET    /api/v1/ab-tests                     - List A/B tests
POST   /api/v1/ab-tests                     - Create A/B test
GET    /api/v1/events/subscriptions         - List event subscriptions
POST   /api/v1/events/subscriptions         - Create event subscription
GET    /api/v1/detectors                    - List DLP detectors
GET    /api/v1/cache/stats                  - Semantic cache stats
GET    /api/v1/guardrails                   - List guardrails
GET    /api/v1/mcp-servers                  - List MCP servers
GET    /api/v1/agents                       - List A2A agents
GET    /api/v1/workflows                    - List workflows
GET    /api/v1/deprecations                 - List model deprecations
GET    /api/v1/settings                     - Platform settings
GET    /api/v1/metrics/realtime             - Real-time metrics
```

---

## Grafana Dashboards (http://localhost:3030)

**Login:** admin / admin@123

| Dashboard | URL | Data Source |
|-----------|-----|-------------|
| AI Control Plane Overview | /d/ai-gateway-overview | Prometheus |
| FinOps Cost Tracking | /d/finops-cost-tracking | PostgreSQL |

### AI Control Plane Overview shows:
- Total Requests, Error Rate, P95 Latency
- Total Spend, Total Tokens
- Request Rate by Model (time series)
- Latency Percentiles by Model
- Request/Spend/Token Distribution (pie charts)

### FinOps Cost Tracking shows:
- Today's/Week's/Total Spend
- Token Usage (Input/Output)
- Spend by Model (pie chart)
- Requests by Model (pie chart)
- Tokens by Model (pie chart)
- Recent Requests Log (table)

---

## Demo Scenario 1: Basic AI Chat

**Tests:** LiteLLM proxy, model routing

```bash
# 1. List available models
curl http://localhost:4000/v1/models \
  -H "Authorization: Bearer $LITELLM_KEY" | jq '.data[].id'

# 2. Chat completion (OpenAI format)
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hello, what is 2+2?"}]
  }' | jq '.choices[0].message'

# 3. Try Claude model
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -d '{
    "model": "claude-3-5-sonnet",
    "messages": [{"role": "user", "content": "Explain quantum computing in one sentence"}]
  }' | jq '.choices[0].message'
```

---

## Demo Scenario 2: Cost Prediction

**Tests:** Cost predictor service, budget awareness

```bash
# 1. Predict cost for a request
curl http://localhost:8080/predict \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "Write a 500 word essay about AI"}],
    "max_tokens": 1000
  }' | jq

# 2. Check budget status
curl http://localhost:8081/budgets | jq
```

---

## Demo Scenario 3: Policy-Based Routing

**Tests:** Cedar policies, smart model selection

```bash
# 1. Check policy router health
curl http://localhost:8084/health | jq

# 2. Request model routing (low budget scenario)
curl http://localhost:8084/route \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "demo-user",
    "team_id": "engineering",
    "requested_model": "smart",
    "budget_remaining": 5.0,
    "latency_sla_ms": 1000
  }' | jq

# 3. Request model routing (high priority scenario)
curl http://localhost:8084/route \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "demo-user",
    "team_id": "engineering",
    "requested_model": "smart",
    "budget_remaining": 100.0,
    "latency_sla_ms": 200
  }' | jq
```

---

## Demo Scenario 4: Workflow Engine

**Tests:** LangGraph workflows, templates

```bash
# 1. Check workflow engine health
curl http://localhost:8085/health | jq

# 2. List available workflow templates
curl http://localhost:8085/api/v1/templates | jq

# 3. Start a research workflow
curl http://localhost:8085/api/v1/executions \
  -H "Content-Type: application/json" \
  -d '{
    "template": "research",
    "input": {
      "query": "What are the latest trends in AI agents?"
    }
  }' | jq

# 4. Check execution status (replace {id} with actual ID)
curl http://localhost:8085/api/v1/executions/{id} | jq
```

---

## Demo Scenario 5: Observability Stack

### Grafana (http://localhost:3030)
- Login: admin / admin@123
- Dashboards: AI Control Plane → AI Control Plane Overview, FinOps Cost Tracking

### Prometheus (http://localhost:9090)
```promql
# Query examples:
litellm_requests_metric_total
litellm_spend_metric_total
litellm_llm_api_latency_metric_bucket
```

### Jaeger (http://localhost:16686)
- Search for traces by service
- View request flow across services

---

## Demo Scenario 6: Vault Secrets

**Tests:** Secrets management, access control

```bash
# 1. Check Vault status
curl http://localhost:8200/v1/sys/health | jq

# 2. List secrets (requires token)
export VAULT_ADDR=http://localhost:8200
export VAULT_TOKEN=root-token-for-dev

vault kv list secret/ai-gateway/dev/

# 3. Read a secret
vault kv get secret/ai-gateway/dev/providers/openai
```

---

## Demo Scenario 7: Enterprise Organization Setup

**Tests:** Multi-tenancy, SSO, team hierarchy

```bash
# 1. Login to Admin API
TOKEN=$(curl -s http://localhost:8086/auth/login \
  -d '{"api_key":"$LITELLM_KEY"}' \
  -H 'Content-Type: application/json' | jq -r .access_token)

# 2. Create organization
curl -X POST http://localhost:8086/api/v1/organizations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Demo Corp", "slug": "demo-corp", "max_budget": 1000}' | jq

# 3. Create business unit
ORG_ID=$(curl -s http://localhost:8086/api/v1/organizations \
  -H "Authorization: Bearer $TOKEN" | jq -r '.[0].id')

curl -X POST "http://localhost:8086/api/v1/organizations/$ORG_ID/business-units" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Engineering", "slug": "engineering", "max_budget": 500}' | jq
```

---

## Demo Scenario 8: Audit & Compliance

**Tests:** Audit logging, change tracking

```bash
# View recent audit events
curl "http://localhost:8086/api/v1/audit-logs?limit=10" \
  -H "Authorization: Bearer $TOKEN" | jq

# Filter by resource type
curl "http://localhost:8086/api/v1/audit-logs?resource_type=organization" \
  -H "Authorization: Bearer $TOKEN" | jq
```

---

## Demo Scenario 9: Chargeback & SLA

**Tests:** Cost allocation, provider health

```bash
# 1. Create cost allocation rule
curl -X POST http://localhost:8086/api/v1/cost-allocation/rules \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Eng to CC-1234", "allocation_type": "cost_center", "allocation_target": "CC-1234"}' | jq

# 2. Check provider health
curl http://localhost:8086/api/v1/sla/health \
  -H "Authorization: Bearer $TOKEN" | jq

# 3. Create SLA definition
curl -X POST http://localhost:8086/api/v1/sla/definitions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "GPT-4o SLA", "provider": "openai", "model_pattern": "gpt-4o*", "target_p95_ms": 3000, "target_error_rate": 0.01}' | jq
```

---

## Demo Scenario 10: A/B Testing & Events

**Tests:** Model comparison, event system

```bash
# 1. Create A/B test
curl -X POST http://localhost:8086/api/v1/ab-tests \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "GPT vs Claude", "base_model": "gpt-4o", "variant_model": "claude-sonnet-4.5", "traffic_split_percent": 20}' | jq

# 2. Create event subscription
curl -X POST http://localhost:8086/api/v1/events/subscriptions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Budget Alerts", "event_types": ["budget.exceeded", "sla.violation"], "channel": "webhook", "config": {"url": "https://httpbin.org/post"}}' | jq

# 3. Send test event
curl -X POST http://localhost:8086/api/v1/events/test \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"event_type": "budget.exceeded", "payload": {"team": "engineering", "amount": 500}}' | jq
```

---

## Troubleshooting

### Service not healthy
```bash
# Check logs
docker compose logs <service-name> --tail 100

# Restart specific service
docker compose restart <service-name>
```

### Database connection issues
```bash
# Check postgres
docker compose exec postgres psql -U litellm -c "SELECT 1"
```

### Reset everything
```bash
docker compose down -v
docker compose up -d
```

---

## Demo Readiness Checklist

- [ ] All services running (`docker compose ps`)
- [ ] Vault initialized with secrets
- [ ] LiteLLM responding to /v1/models
- [ ] Admin UI accessible at :5173
- [ ] Grafana dashboards showing data at :3030
- [ ] At least one chat completion working
- [ ] Organizations page shows at least one org
- [ ] Audit log has entries from setup operations
- [ ] Chargeback allocation rules configured
- [ ] SLA definitions created
- [ ] Event subscriptions active
