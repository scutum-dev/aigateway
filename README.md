# AI Control Plane Platform

A unified AI infrastructure platform with 100+ models across 9 providers. Features intelligent routing, workflow orchestration, semantic caching, and enterprise-grade cost management.

**Supported Providers:** OpenAI, Anthropic, Google, xAI, DeepSeek, AWS Bedrock, Google Vertex AI, Azure OpenAI, Ollama

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENTS / APPS                                  │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────────────┐
│                         Nginx Ingress (Port 80/443)                          │
│  /v1/* → LiteLLM  |  /mcp/* → Agent Gateway  |  /admin-ui/* → Admin UI      │
└────────┬──────────────────────────┬──────────────────────────┬──────────────┘
         │                          │                          │
┌────────▼────────┐    ┌───────────▼───────────┐    ┌────────▼────────┐
│   LiteLLM       │    │    Agent Gateway      │    │   Admin UI      │
│   Port 4000     │◄───│    Port 9000          │    │   Port 5173     │
│                 │    │  MCP + A2A Protocols  │    │   (React/Vite)  │
└────────┬────────┘    └───────────┬───────────┘    └────────┬────────┘
         │                         │                          │
         ▼                         ▼                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PLATFORM SERVICES                                  │
├─────────────────┬─────────────────┬─────────────────┬───────────────────────┤
│ Policy Router   │ Workflow Engine │ Gateway         │ Admin API             │
│ Port 8084       │ Port 8085       │ Abstraction     │ Port 8086             │
│                 │                 │ (Python Module) │                       │
│ • Cedar eval    │ • LangGraph     │ • AbstractGW    │ • Model config        │
│ • Model select  │ • Templates     │ • Adapters      │ • Budget mgmt         │
│ • Metrics cache │ • Checkpoints   │ • Registry      │ • Team mgmt           │
│ • Routing rules │ • MCP binding   │ • Plugin disc.  │ • MCP config          │
└────────┬────────┴────────┬────────┴────────┬────────┴──────────┬────────────┘
         │                 │                 │                   │
         └────────────────┬┴─────────────────┴┬──────────────────┘
                          │                   │
               ┌──────────▼──────────┐  ┌────▼────┐
               │     PostgreSQL      │  │  Redis  │
               │  • routing_decisions│  │ Cache   │
               │  • workflow_*       │  │         │
               │  • budgets/teams    │  │         │
               └─────────────────────┘  └─────────┘
```

## Documentation

| Guide | Description |
|-------|-------------|
| **[Quickstart](docs/guides/QUICKSTART.md)** | Get running in 5 minutes with Docker |
| **[API Integration](docs/guides/API_INTEGRATION.md)** | Code examples in Python, TypeScript, Go, and curl |
| **[Model Routing](docs/guides/MODEL_ROUTING.md)** | How intelligent model selection works |
| **[Cost Management](docs/guides/COST_MANAGEMENT.md)** | Budgets, alerts, and FinOps reporting |
| **[Admin UI Guide](docs/guides/ADMIN_GUIDE.md)** | Page-by-page walkthrough of the Admin Console |

## Components

| Component | Port | Description |
|-----------|------|-------------|
| **Agent Gateway** | 9000 | Rust-based data plane for MCP/A2A protocols, LLM routing |
| **LiteLLM** | 4000 | Cost tracking, budgets, provider routing |
| **Policy Router** | 8084 | Cedar policy-based intelligent model routing |
| **Workflow Engine** | 8085 | LangGraph-based workflow orchestration |
| **Admin API** | 8086 | REST API for platform configuration |
| **Admin UI** | 5173 | React-based administration dashboard |
| **Semantic Cache** | 8083 | Embedding-based prompt caching for cost savings |
| **A2A Runtime** | 8087 | Temporal-based agent orchestration |
| **Temporal** | 7233 | Durable workflow execution engine |
| **Temporal UI** | 8088 | Workflow monitoring dashboard |
| **vLLM** | - | Self-hosted LLM inference (optional) |
| **PostgreSQL** | 5432 | Spend tracking, workflows, configuration |
| **Redis** | 6379 | Caching, semantic vectors, metrics |
| **Prometheus** | 9090 | Metrics collection and alerting |
| **Grafana** | 3030 | Dashboards and visualization |
| **Jaeger** | 16686 | Distributed tracing |

## Features

### Cedar Policy-Driven Model Routing
Intelligent model selection based on:
- **Cost thresholds** - Route to budget-friendly models when spend limits approach
- **Latency SLAs** - Ensure models meet response time requirements
- **Team quotas** - Enforce per-team model access and budgets
- **Circuit breaking** - Automatic failover when error rates spike
- **Provider preferences** - Route to preferred providers by use case

### LangGraph Workflow Engine
Pre-built templates for common AI workflows:
- **Research Agent** - Web search, analysis, report generation
- **Coding Agent** - Code understanding, generation, review (with iteration)
- **Data Analysis Agent** - SQL generation, data analysis, visualization

Features:
- PostgreSQL checkpointing for resumable workflows
- WebSocket streaming for real-time updates
- Per-workflow cost tracking
- MCP tool integration

### Gateway Abstraction Layer
Pluggable interface for AI gateways with 8 adapters:
- **LiteLLM** - Primary gateway with full feature support
- **OpenAI** - Direct OpenAI API access
- **Anthropic** - Direct Anthropic Claude API
- **Azure OpenAI** - Azure-hosted OpenAI models
- **AWS Bedrock** - Claude, Llama, Titan on AWS
- **Google Vertex AI** - Gemini and PaLM models
- **Ollama** - Local open-source models
- **Custom** - Template for custom backends

Features:
- Unified request/response models
- Configuration-based gateway selection
- Automatic capability discovery
- Model-to-gateway routing rules

### Semantic Caching
Intelligent prompt-level caching for cost savings:
- **Embedding-based similarity** - Find similar prompts using vector search
- **Configurable thresholds** - Set similarity threshold (default: 0.92)
- **TTL-based expiration** - Automatic cache cleanup
- **Per-model isolation** - Separate caches per model
- **Cache statistics** - Track hits, misses, tokens saved

### A2A Runtime (Temporal)
Durable agent-to-agent orchestration:
- **Single Agent** - Simple agent invocation with retries
- **Sequential Pipeline** - Chain agents in sequence
- **Parallel Execution** - Run multiple agents concurrently
- **Supervisor Pattern** - Coordinator agent managing workers
- **Human-in-Loop** - Approval workflows with timeout

Features:
- Automatic retries with backoff
- Execution history and audit logging
- Agent registry with capability discovery
- Message routing between agents

### Admin Configuration UI
Web-based platform management:
- Model routing policy editor
- Budget management with spend tracking
- Team and user management
- MCP server configuration
- Real-time metrics dashboard
- Platform settings

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Kubernetes cluster (for production)
- kubectl & kustomize
- API keys for OpenAI/Anthropic (optional)

### Local Development

1. **Clone and setup:**
   ```bash
   cd gateway
   cp config/.env.example config/.env
   ```

2. **Set environment variables in `config/.env`:**
   ```bash
   OPENAI_API_KEY=sk-...
   ANTHROPIC_API_KEY=sk-ant-...
   XAI_API_KEY=xai-...
   ```

3. **Start with Docker Compose:**
   ```bash
   docker-compose up -d
   ```

4. **Access the services:**
   - Admin UI: http://localhost:5173
   - Agent Gateway: http://localhost:9000
   - Grafana: http://localhost:3030 (admin/admin)
   - Jaeger: http://localhost:16686

5. **Test the API:**
   ```bash
   # Test LLM API via Agent Gateway
   curl http://localhost:9000/v1/chat/completions \
     -H "Authorization: Bearer $LITELLM_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "model": "gpt-4o-mini",
       "messages": [{"role": "user", "content": "Hello!"}]
     }'

   # Test Policy Router
   curl http://localhost:8084/route \
     -H "Content-Type: application/json" \
     -d '{
       "user_id": "test-user",
       "team_id": "engineering",
       "requested_model": "smart",
       "budget_remaining": 100.0,
       "latency_sla_ms": 5000
     }'

   # Start a workflow
   curl http://localhost:8085/api/v1/executions \
     -H "Content-Type: application/json" \
     -d '{
       "template": "research",
       "input": {"query": "AI gateway architectures"},
       "user_id": "test-user"
     }'

   # Login to Admin API
   curl http://localhost:8086/auth/login \
     -H "Content-Type: application/json" \
     -d '{"api_key": "$LITELLM_KEY"}'
   ```

### Cloud Deployment (GCP)

Single-command deployment using Terraform:

```bash
make demo           # Deploy demo environment
make staging        # Deploy staging environment
make prod           # Deploy production (requires confirmation)
make demo-destroy   # Tear down demo
```

See [Cloud Deployment Guide](docs/CLOUD_DEPLOYMENT.md) for full documentation.

### Local Kubernetes Deployment

```bash
kubectl apply -k kubernetes/overlays/dev        # Development
kubectl apply -k kubernetes/overlays/staging    # Staging
kubectl apply -k kubernetes/overlays/production # Production
```

## API Reference

### LLM API (Port 9000)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/chat/completions` | Chat completion (OpenAI-compatible) |
| POST | `/v1/embeddings` | Text embeddings |
| GET | `/v1/models` | List available models |
| GET | `/health` | Health check |

### Policy Router (Port 8084)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/route` | Get routing decision for a request |
| POST | `/evaluate` | Direct Cedar policy evaluation |
| POST | `/policies/reload` | Hot-reload Cedar policies |
| GET | `/models` | List models with current metrics |
| GET | `/health` | Health check |

### Workflow Engine (Port 8085)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/templates` | List workflow templates |
| POST | `/api/v1/workflows` | Create workflow definition |
| GET | `/api/v1/workflows` | List workflows |
| POST | `/api/v1/executions` | Start workflow execution |
| GET | `/api/v1/executions/{id}` | Get execution status |
| GET | `/api/v1/executions/{id}/steps` | Get step details |
| POST | `/api/v1/executions/{id}/pause` | Pause execution |
| POST | `/api/v1/executions/{id}/resume` | Resume execution |
| GET | `/api/v1/costs/summary` | Cost summary |
| WS | `/ws/executions/{id}` | Stream execution updates |

### Admin API (Port 8086)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/login` | Authenticate with API key |
| GET | `/api/v1/models` | List model configurations |
| GET/PUT | `/api/v1/routing-policies` | Routing policy CRUD |
| GET/POST | `/api/v1/budgets` | Budget management |
| GET/POST | `/api/v1/teams` | Team management |
| PUT/DELETE | `/api/v1/teams/{team_id}` | Update/delete a team |
| GET | `/api/v1/guardrail-assignments` | List guardrail-to-team assignments |
| GET/POST | `/api/v1/mcp-servers` | MCP server configuration |
| GET/POST | `/api/v1/workflows` | Workflow templates |
| GET | `/api/v1/metrics/realtime` | Real-time metrics |
| GET/PUT | `/api/v1/settings` | Platform settings |

### Semantic Cache (Port 8083)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/lookup` | Look up cached response by semantic similarity |
| POST | `/store` | Store response in cache |
| DELETE | `/invalidate/{cache_key}` | Invalidate specific cache entry |
| DELETE | `/invalidate-model/{model}` | Invalidate all entries for a model |
| DELETE | `/invalidate-user/{user_id}` | Invalidate all entries for a user |
| GET | `/stats` | Get cache statistics (hits, misses, savings) |
| POST | `/warmup` | Warm up cache with pre-computed entries |
| POST | `/similarity` | Compute semantic similarity between texts |
| GET | `/health` | Health check |

### A2A Runtime (Port 8087)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/agents/register` | Register an agent |
| DELETE | `/agents/{agent_id}` | Unregister an agent |
| POST | `/agents/{agent_id}/heartbeat` | Update agent heartbeat |
| GET | `/agents` | List registered agents |
| GET | `/capabilities` | List all capabilities |
| POST | `/workflows/start` | Start A2A workflow |
| GET | `/workflows/{workflow_id}` | Get workflow status |
| POST | `/workflows/{workflow_id}/cancel` | Cancel workflow |
| GET | `/workflows/{workflow_id}/history` | Get execution history |
| POST | `/approvals` | Submit human approval |
| GET | `/approvals/pending` | List pending approvals |
| POST | `/messages` | Send message between agents |
| GET | `/health` | Health check |

## Configuration

### Cedar Routing Policies

Located in `config/agentgateway/policies/routing-rules.cedar`:

```cedar
// Prefer self-hosted when budget is low
@priority(100)
permit (principal, action == "routing:select_model", resource)
when {
    context.cost_budget_remaining < 10.0 &&
    resource.provider == "vllm"
};

// Forbid slow models for tight latency SLAs
@priority(85)
forbid (principal, action == "routing:select_model", resource)
when {
    context.latency_sla_ms < 500 &&
    resource.average_latency_ms > context.latency_sla_ms
};

// Circuit breaker for high error rates
forbid (principal, action == "routing:select_model", resource)
when { resource.current_error_rate > 0.05 };
```

### Gateway Abstraction

Located in `config/gateway-abstraction/gateways.yaml`:

```yaml
default_gateway: litellm

gateways:
  - type: litellm
    name: primary-litellm
    base_url: http://litellm:4000
    api_key: ${LITELLM_MASTER_KEY}

  - type: openai
    name: direct-openai
    base_url: https://api.openai.com/v1
    api_key: ${OPENAI_API_KEY}

routing:
  strategy: priority
  model_routing:
    "gpt-*": [primary-litellm, direct-openai]
    "claude-*": [primary-litellm]
    "*": [primary-litellm]
```

### LiteLLM Configuration

See `config/litellm/config.yaml` for model routing, pricing, and budget configuration.

### Agent Gateway Configuration

See `config/agentgateway/config.yaml` for backend configuration, auth, and policies.

## Directory Structure

```
gateway/
├── kubernetes/
│   ├── base/                    # Base Kubernetes manifests
│   │   ├── agentgateway/        # Agent Gateway deployment
│   │   ├── litellm/             # LiteLLM deployment
│   │   ├── vllm/                # vLLM Helm values
│   │   ├── observability/       # OTEL, Prometheus, Grafana
│   │   └── database/            # PostgreSQL
│   └── overlays/
│       ├── dev/                 # Development overrides
│       ├── staging/             # Staging overrides
│       └── production/          # Production overrides
├── config/
│   ├── litellm/config.yaml      # LiteLLM configuration
│   ├── agentgateway/
│   │   ├── config.yaml          # Agent Gateway configuration
│   │   └── policies/            # Cedar routing policies
│   ├── gateway-abstraction/     # Gateway abstraction config
│   ├── otel/                    # OpenTelemetry configuration
│   └── nginx/                   # Nginx reverse proxy config
├── src/
│   ├── cost-predictor/          # Cost prediction service
│   ├── budget-webhook/          # Budget enforcement webhook
│   ├── finops-reporter/         # FinOps reporting service
│   ├── policy-router/           # Cedar policy-based routing
│   ├── workflow-engine/         # LangGraph workflow orchestration
│   ├── admin-api/               # Admin REST API
│   └── gateway-abstraction/     # Gateway abstraction module
├── ui/
│   └── admin/                   # Admin UI (React + Vite)
├── tests/
│   ├── integration/             # Integration tests
│   ├── load/k6/                 # k6 load tests
│   └── e2e/                     # End-to-end tests
├── docker-compose.yaml          # Local development setup
└── README.md
```

## Testing

### Integration Tests

```bash
# Run all integration tests
cd tests
pip install -r requirements.txt
pytest integration/ -v

# Run specific service tests
pytest integration/test_policy_router.py -v
pytest integration/test_workflow_engine.py -v
pytest integration/test_admin_api.py -v
pytest integration/test_gateway_abstraction.py -v
```

### Load Tests

```bash
cd tests/load/k6
k6 run load_test.js
```

### E2E Tests

```bash
cd tests
pytest e2e/ -v
```

## Monitoring

### Grafana Dashboards
- **AI Control Plane Overview** - Request rates, latencies, costs
- **vLLM Performance** - GPU utilization, queue depth
- **Budget Alerts** - Budget utilization by user/team
- **Workflow Metrics** - Execution counts, durations, costs

### Prometheus Alerts
- `HighErrorRate` - Error rate > 5%
- `HighLatency` - P95 latency > 2s
- `BudgetExhausted` - Budget limit reached
- `WorkflowFailed` - Workflow execution failed

## Supported Models

### Direct Providers
| Provider | Models |
|----------|--------|
| **OpenAI** | GPT-5, GPT-5.2, GPT-5-mini, o3, o3-pro, o4-mini, GPT-4o, GPT-4o-mini |
| **Anthropic** | Claude Opus 4.5, Claude Sonnet 4.5, Claude Haiku 4.5, Claude Opus 4, Claude Sonnet 4 |
| **Google** | Gemini 3 Pro, Gemini 3 Flash, Gemini 2.5 Pro/Flash/Flash-Lite |
| **xAI** | Grok 4, Grok 4 Heavy, Grok 3, Grok 3 Mini |
| **DeepSeek** | DeepSeek V3, DeepSeek R1, DeepSeek Coder |

### Cloud Platforms
| Provider | Models |
|----------|--------|
| **AWS Bedrock** | Claude 4.5, Llama 4 (405b/70b), Llama 3.3/3.2/3.1, Mistral Large 3, Nova Pro/Lite/Micro, Titan, DeepSeek R1, Cohere Command R+, AI21 Jamba |
| **Google Vertex AI** | Gemini 3/2.5 Pro/Flash, Claude Opus/Haiku 4.5, DeepSeek V3.2 |
| **Azure OpenAI** | GPT-5.2/5.1, GPT-4.1, o4-mini, o3, o3-mini, o1, GPT-4o, embeddings, audio models |

### Local Models (Ollama)
| Model | Requirements |
|-------|--------------|
| Llama 3.1 70B/8B | GPU with 48GB+ / 8GB+ VRAM |
| Mistral, CodeLlama | GPU with 8GB+ VRAM |

## Model Groups

Use model aliases for semantic routing:
- `fast` - GPT-5-mini, Claude Haiku 4.5, Gemini 3 Flash, Grok 3 Mini
- `smart` - GPT-5, Claude Sonnet 4.5, Gemini 3 Pro, Grok 4
- `powerful` - GPT-5.2, Claude Opus 4.5, o3-pro, Grok 4 Heavy
- `reasoning` - o3, o3-pro, DeepSeek R1
- `coding` - Claude Sonnet 4.5, DeepSeek Coder, CodeLlama
- `cost-effective` - GPT-5-mini, Claude Haiku 4.5, Gemini 2.5 Flash-Lite, DeepSeek V3
- `bedrock` - All AWS Bedrock models
- `vertex` - All Google Vertex AI models
- `azure` - All Azure OpenAI models
- `local` - Ollama models (Llama, Mistral, CodeLlama)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes and add tests
4. Submit a pull request

## License

MIT License

## References

- [Agent Gateway](https://agentgateway.dev)
- [LiteLLM Documentation](https://docs.litellm.ai)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Cedar Policy Language](https://www.cedarpolicy.com/)
- [vLLM Production Stack](https://docs.vllm.ai/projects/production-stack)
- [OpenTelemetry](https://opentelemetry.io)
