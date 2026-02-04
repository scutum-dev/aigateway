# AI Gateway Demo Runbook

## Quick Status Check

```bash
# Check all services
docker compose ps

# Expected: 22 services, 21+ healthy
```

## Service Endpoints

| Service | URL | Credentials |
|---------|-----|-------------|
| Landing Page | http://localhost:9999 | - |
| **Admin UI** | http://localhost:5173 | API Key: `$LITELLM_KEY` |
| Admin API (Swagger) | http://localhost:8086/docs | - |
| LiteLLM API | http://localhost:4000 | `$LITELLM_KEY` |
| LiteLLM UI | http://localhost:4000/ui | `$LITELLM_KEY` |
| Agent Gateway | http://localhost:9000 | - |
| **Grafana** | http://localhost:3030 | admin / admin@123 |
| Prometheus | http://localhost:9090 | - |
| Jaeger | http://localhost:16686 | - |
| Vault | http://localhost:8200 | Token: `root-token-for-dev` |
| Temporal UI | http://localhost:8088 | - |
| Cost Predictor | http://localhost:8080 | - |
| Budget Webhook | http://localhost:8081 | - |
| FinOps Reporter | http://localhost:8082 | - |
| Semantic Cache | http://localhost:8083 | - |
| Policy Router | http://localhost:8084 | - |
| Workflow Engine | http://localhost:8085 | - |

---

## Admin UI Features (http://localhost:5173)

**Login:** Use API key `$LITELLM_KEY`

### What you can do:

| Feature | Description |
|---------|-------------|
| **Dashboard** | Real-time metrics overview |
| **Models** | View/configure model routing |
| **Routing Policies** | Create Cedar-based routing rules |
| **Budgets** | Set spending limits per user/team |
| **Teams** | Manage teams and members |
| **MCP Servers** | Configure MCP tool servers |
| **Workflows** | View workflow templates |
| **Settings** | Platform configuration |

### Admin API Endpoints (http://localhost:8086/docs)

```
POST   /auth/login              - Login with API key
GET    /auth/me                 - Get current user info
GET    /api/v1/models           - List models
PUT    /api/v1/models/{id}      - Update model config
GET    /api/v1/routing-policies - List routing policies
POST   /api/v1/routing-policies - Create routing policy
GET    /api/v1/budgets          - List budgets
POST   /api/v1/budgets          - Create budget
GET    /api/v1/teams            - List teams
POST   /api/v1/teams            - Create team
GET    /api/v1/mcp-servers      - List MCP servers
GET    /api/v1/workflows        - List workflows
GET    /api/v1/metrics/realtime - Real-time metrics
GET    /api/v1/settings         - Platform settings
```

---

## Grafana Dashboards (http://localhost:3030)

**Login:** admin / admin@123

| Dashboard | URL | Data Source |
|-----------|-----|-------------|
| AI Gateway Overview | /d/ai-gateway-overview | Prometheus |
| FinOps Cost Tracking | /d/finops-cost-tracking | PostgreSQL |

### AI Gateway Overview shows:
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
- Dashboards: AI Gateway → AI Gateway Overview, FinOps Cost Tracking

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
