# Model Routing Guide

The AI Control Plane routes every LLM request through an intelligent pipeline that selects the best available model, applies policies, and handles failures automatically. This guide explains how routing works and how to configure it.

## How a Request is Routed

When your application sends a request to `POST /v1/chat/completions` with a model name, the gateway processes it through these stages:

1. **Alias resolution** -- the model name is matched to one or more concrete models
2. **Availability check** -- unhealthy or rate-limited models are filtered out
3. **Policy evaluation** -- routing rules determine which models are permitted
4. **Usage-based ranking** -- eligible models are scored by current load and usage
5. **Request dispatch** -- the top-ranked model receives the request
6. **Fallback** -- if the selected model fails, the next model in the chain is tried

All of this happens in a single request. Your application receives a response from whichever model ultimately serves it.

## Model Groups

Models are organized into groups by capability and provider. When you request a group alias, the gateway routes to one of the models in that group based on availability and load.

### Capability Groups

| Group          | Models Included                                                  | Use Case                     |
|----------------|------------------------------------------------------------------|------------------------------|
| `fast`         | gpt-5-mini, claude-haiku-4.5, gemini-3-flash, grok-3-mini       | Low-latency responses       |
| `smart`        | gpt-5, claude-sonnet-4.5, gemini-3-pro, grok-4                  | Balanced quality and speed  |
| `powerful`     | gpt-5.2, claude-opus-4.5, o3-pro, grok-4-heavy                  | Maximum capability          |
| `reasoning`    | o3, o3-pro, deepseek-r1                                         | Complex multi-step reasoning|
| `coding`       | claude-sonnet-4.5, deepseek-coder, codellama                    | Code generation and review  |
| `cost-effective`| gpt-5-mini, claude-haiku-4.5, gemini-2.5-flash-lite, deepseek-v3| Budget-optimized workloads  |

### Provider Groups

| Group      | Models Included                                                  |
|------------|------------------------------------------------------------------|
| `openai`   | gpt-5, gpt-5.2, gpt-5-mini, o3, o4-mini                        |
| `anthropic`| claude-opus-4.5, claude-sonnet-4.5, claude-haiku-4.5             |
| `google`   | gemini-3-pro, gemini-3-flash, gemini-2.5-pro                    |
| `xai`      | grok-4, grok-4-heavy, grok-3                                    |
| `deepseek` | deepseek-v3, deepseek-r1, deepseek-coder                        |
| `bedrock`  | bedrock-claude-opus-4.5, bedrock-llama-4-405b, bedrock-nova-pro, and more |
| `vertex`   | vertex-gemini-3-pro, vertex-claude-opus-4.5, vertex-deepseek-v3, and more |
| `azure`    | azure-gpt-5.2, azure-gpt-4.1, azure-o4-mini, and more          |

You can request any group or individual model by name:

```bash
# Use a specific model
curl -d '{"model": "claude-sonnet-4.5", ...}' ...

# Use a capability group
curl -d '{"model": "fast", ...}' ...

# Use a provider group
curl -d '{"model": "anthropic", ...}' ...
```

## Alias Resolution

When the gateway receives a model name, it resolves it in this order:

1. **Exact match** -- if the name matches a configured model (e.g., `gpt-5`), that model is used directly.
2. **Group alias** -- if the name matches a model group (e.g., `fast`), the gateway has multiple candidate models to choose from.
3. **Legacy alias** -- some old model names redirect to newer versions. For example, `claude-3-5-sonnet` routes to `claude-sonnet-4.5` and `claude-3-haiku` routes to `claude-haiku-4.5`.

If the name does not match anything, the gateway returns a 404 error.

## Availability Checks

Before routing, the gateway filters out models that are currently unavailable:

- **Health checks**: The gateway runs background health checks against every model provider every 2 hours. Models that fail their health check are marked unhealthy and excluded from routing until they recover.
- **Rate limit detection**: If a provider returns a 429 (rate limited) response, that model is temporarily excluded from the candidate pool for the TTL period (60 seconds by default).
- **RPM/TPM tracking**: The gateway tracks requests per minute and tokens per minute for each model. Models that have exceeded their limits are skipped.

This means if one provider has an outage, your requests automatically flow to healthy alternatives without any action on your part.

## Policy Evaluation

Routing policies add rules that control which models can serve a request. Policies are evaluated in priority order and can permit or deny specific models based on conditions.

Common policy scenarios:

- **Cost control**: Restrict certain teams to cost-effective models only.
- **Latency requirements**: Only allow models that meet a latency SLA (e.g., under 5000ms).
- **Provider preference**: Prioritize a specific provider for compliance or data residency reasons.
- **Circuit breaking**: Automatically disable a model if its error rate exceeds a threshold.

Policies are managed through the Admin UI (Models page) or the Admin API:

```bash
# Create a policy via API
TOKEN="your-jwt-token"

curl http://localhost:8086/api/v1/routing-policies \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "Cost control for interns",
    "description": "Restrict intern team to cost-effective models",
    "priority": 10,
    "condition": "team == intern",
    "action": "permit",
    "target_models": ["gpt-5-mini", "claude-haiku-4.5", "gemini-2.5-flash-lite"]
  }'
```

Policies are evaluated from highest to lowest priority. The first matching policy determines the permitted model set.

## Cedar Policy Engine

The platform ships with [Cedar](https://www.cedarpolicy.com/) routing policies in `config/agentgateway/policies/routing-rules.cedar`. Cedar is Amazon's open-source authorization policy language, providing declarative, auditable rules that go beyond simple allow/deny.

These policies are used by the Agent Gateway for request-level authorization and routing decisions. See the [Agent Gateway Deep Dive](./agentgateway-integration.md) for integration details.

### Cedar Policy Syntax

Cedar policies use a `permit`/`forbid` model. Each policy has:

- **Effect**: `permit` (allow) or `forbid` (deny)
- **Principal**: Who is making the request (user or team)
- **Action**: What operation (`routing:select_model`)
- **Resource**: The model being evaluated
- **Conditions**: `when` clauses that check context and resource attributes

```cedar
// Block premium models when budget is very low
@id("cost-003")
forbid (principal, action == Action::"routing:select_model", resource)
when {
    context.cost_budget_remaining < 5.0 &&
    resource.tier == "premium"
};
```

### Built-In Policy Rules

The platform ships with routing policies in `config/agentgateway/policies/routing-rules.cedar`:

**Cost-Based Routing:**

| Rule | Trigger | Effect |
|------|---------|--------|
| `cost-001` | Budget < $10 remaining | Permit self-hosted models (vLLM) |
| `cost-002` | Budget between $10-$50 | Permit budget/free tier models only |
| `cost-003` | Budget < $5 remaining | Forbid premium models |

**Latency SLA Enforcement:**

| Rule | Trigger | Effect |
|------|---------|--------|
| `latency-001` | Model latency exceeds request SLA | Forbid that model |
| `latency-002` | Request needs < 1000ms, model is < 500ms | Permit (prefer fast models) |

**Circuit Breaker:**

| Rule | Trigger | Effect |
|------|---------|--------|
| `circuit-001` | Model error rate > 5% | Forbid (soft circuit break) |
| `circuit-002` | Model error rate > 10% | Forbid (hard circuit break) |

**Priority-Based:**

| Rule | Trigger | Effect |
|------|---------|--------|
| `priority-001` | High priority request | Permit premium models regardless of budget |
| `priority-002` | Low priority request | Permit budget/free/self-hosted models only |

**Default:**

| Rule | Trigger | Effect |
|------|---------|--------|
| `default-001` | Always | Permit (ensures requests aren't blocked by default) |

`forbid` rules override `permit` rules -- so `circuit-001` will block a model even if `default-001` permits it.

### Writing Custom Cedar Policies

Add `.cedar` files to `config/agentgateway/policies/`:

```cedar
// Restrict the "interns" team to budget models only
@id("team-interns-001")
forbid (principal == team::"interns", action == Action::"routing:select_model", resource)
when {
    resource.tier == "premium"
};

// Force compliance team to use Anthropic models (data residency)
@id("compliance-001")
forbid (principal == team::"compliance", action == Action::"routing:select_model", resource)
when {
    resource.provider != "anthropic"
};
```

### Managing Routing Policies via Admin API

The Admin API provides CRUD endpoints for routing policies stored in the database:

```bash
# List all routing policies
curl http://localhost:8086/api/v1/routing-policies \
  -H "Authorization: Bearer $TOKEN"

# Create a routing policy
curl -X POST http://localhost:8086/api/v1/routing-policies \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "Cost control for interns",
    "description": "Restrict intern team to cost-effective models",
    "priority": 10,
    "condition": "team == intern",
    "action": "permit",
    "target_models": ["gpt-5-mini", "claude-haiku-4.5", "gemini-2.5-flash-lite"]
  }'

# Delete a routing policy
curl -X DELETE http://localhost:8086/api/v1/routing-policies/{policy_id} \
  -H "Authorization: Bearer $TOKEN"
```

## Usage-Based Ranking

After filtering for availability and policy, the gateway ranks the remaining candidate models using a usage-based routing strategy. This means:

- Models with **lower current utilization** (fewer active requests) are preferred.
- The gateway tracks RPM (requests per minute) and TPM (tokens per minute) for each model.
- Load is balanced across models in a group so no single provider gets overwhelmed.
- The ranking refreshes every 60 seconds.

This approach distributes traffic evenly and prevents hot-spotting on a single provider.

## Automatic Fallback Chains

If the selected model fails (provider error, timeout, or rate limit), the gateway automatically retries with the next model in the fallback chain. This happens transparently within the same API call.

### Retry Behavior

- **Max retries**: 3 attempts (configurable)
- **Backoff**: Exponential backoff starting at 1 second
- **Pre-call checks**: The gateway verifies model availability before each retry, skipping known-unhealthy models.

### Default Fallback Chains

| Primary Model      | Fallback 1          | Fallback 2          | Fallback 3       |
|--------------------|---------------------|---------------------|------------------|
| gpt-5              | gpt-5.2             | claude-opus-4.5     | grok-4           |
| gpt-5-mini         | o4-mini             | claude-haiku-4.5    | gemini-3-flash   |
| o3                 | o3-pro              | gpt-5               | deepseek-r1      |
| claude-opus-4.5    | claude-sonnet-4.5   | gpt-5               | grok-4           |
| claude-sonnet-4.5  | claude-opus-4.5     | gpt-5               | gemini-3-pro     |
| claude-haiku-4.5   | gpt-5-mini          | gemini-3-flash      | --               |
| gemini-3-pro       | gemini-2.5-pro      | claude-sonnet-4.5   | gpt-5            |
| gemini-3-flash     | gemini-2.5-flash    | claude-haiku-4.5    | gpt-5-mini       |
| grok-4             | grok-3              | gpt-5               | claude-opus-4.5  |
| deepseek-v3        | deepseek-r1         | gpt-4o              | claude-sonnet-4.5|
| deepseek-r1        | o3                  | deepseek-v3         | --               |

Fallback chains cross provider boundaries. A request for an Anthropic model can fall back to OpenAI or Google, ensuring maximum availability.

## Configuring Routing

### Through the Admin UI

1. Open **http://localhost:5173** and log in.
2. Navigate to **Models** to see all configured models with their provider, tier, cost, and latency SLA.
3. Click the edit icon on any model to change its tier, latency SLA, or active status.
4. Navigate to **Settings** to adjust global routing behavior:
   - **Enable Routing Policies** -- toggle policy-based routing on or off.
   - **Default Model** -- the model used when no model is specified in the request.
   - **Global Rate Limit** -- platform-wide requests per minute cap.

### Through the Admin API

```bash
# List all routing policies
curl http://localhost:8086/api/v1/routing-policies \
  -H "Authorization: Bearer $TOKEN"

# Update a model's configuration
curl -X PUT http://localhost:8086/api/v1/models/gpt-5 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "tier": "premium",
    "default_latency_sla_ms": 10000
  }'

# Delete a routing policy
curl -X DELETE http://localhost:8086/api/v1/routing-policies/{policy_id} \
  -H "Authorization: Bearer $TOKEN"
```

### Through the Config File

Model definitions and fallback chains are declared in `config/litellm/config.yaml`. The `router_settings` section controls the routing strategy, retry policy, fallback chains, and model group aliases.

Changes to the config file take effect on the next container restart:

```bash
docker compose --env-file config/.env restart litellm
```

## Observing Routing Decisions

To understand how requests are being routed:

- **Response metadata**: The `model` field in every API response shows which model actually served the request.
- **Admin Dashboard**: The Dashboard in the Admin UI shows a model usage breakdown chart for the current day.
- **Observability stack**: Enable the `observability` profile to get detailed traces in Jaeger (http://localhost:16686) and metrics in Grafana (http://localhost:3030).

```bash
docker compose --env-file config/.env --profile observability up -d
```

## Best Practices

- **Use group aliases** (`fast`, `smart`, `powerful`) instead of pinning to specific models. This gives the gateway flexibility to route around failures and balance load.
- **Set latency SLAs** on models to match your application requirements. The gateway will prefer models that meet the SLA.
- **Keep fallback chains cross-provider** so that a single provider outage does not take down your application.
- **Use Cedar policies for complex rules** -- team restrictions, compliance constraints, and budget-aware routing are best expressed as declarative policies rather than code changes.
- **Monitor the dashboard** regularly to spot unexpected routing patterns or cost spikes.
- **Check routing decisions** via the `/decisions` endpoint to audit why specific models were selected or rejected.

## Related Guides

- [Cost Management](./cost-management.md) -- budgets, alerts, and FinOps reporting
- [Observability](./observability.md) -- Grafana dashboards and Prometheus metrics that feed into routing decisions
- [API Integration](./api-integration.md) -- how to send requests through the gateway
