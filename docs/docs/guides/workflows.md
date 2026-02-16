# Workflows Guide

Build and execute multi-step AI workflows using LangGraph templates and Temporal orchestration.

## Overview

The workflow engine provides pre-built workflow templates that chain multiple LLM calls into structured pipelines. Each workflow breaks a complex task into discrete steps -- research, analysis, generation, review -- with automatic state management and error handling.

### Architecture

```
Admin UI / API ──▶ Workflow Engine (:8085) ──▶ LiteLLM (:4000) ──▶ AI Providers
                         │
                         ├── LangGraph (workflow graphs)
                         ├── Temporal (orchestration, retries)
                         └── PostgreSQL (execution history)
```

## Enabling Workflows

Start the workflow services:

```bash
docker compose --env-file config/.env --profile workflows up -d
```

This starts:

| Service | Port | Description |
|---------|------|-------------|
| Workflow Engine | 8085 | LangGraph workflow execution |
| A2A Runtime | 8087 | Temporal agent-to-agent workflows |
| Temporal | 7233 | Workflow orchestration server |
| Temporal UI | 8088 | Temporal web dashboard |

## Pre-built Templates

Three workflow templates are available out of the box:

### Research Agent

Multi-source research with web search and report generation.

**Nodes:** `parse_query` → `search_web` → `search_database` → `analyze_results` → `generate_report`

**Use case:** Market research, competitive analysis, literature review.

```bash
curl -X POST http://localhost:8086/api/v1/workflow-executions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_name": "Research Agent",
    "template": "research",
    "input_data": {
      "prompt": "Research the current state of AI gateway products in the market"
    }
  }'
```

### Coding Agent

Iterative code generation with analysis and review.

**Nodes:** `understand_task` → `read_code` → `generate_code` → `analyze_code` → `finalize_code`

**Use case:** Code generation, refactoring, code review.

```bash
curl -X POST http://localhost:8086/api/v1/workflow-executions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_name": "Coding Agent",
    "template": "coding",
    "input_data": {
      "prompt": "Write a Python function that implements binary search with error handling"
    }
  }'
```

### Data Analysis

SQL generation, analysis, and visualization.

**Nodes:** `parse_question` → `query_data` → `analyze_data` → `generate_visualization` → `summarize`

**Use case:** Business intelligence, data exploration, report generation.

```bash
curl -X POST http://localhost:8086/api/v1/workflow-executions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_name": "Data Analysis",
    "template": "data-analysis",
    "input_data": {
      "prompt": "Analyze our API spending trends by model over the last 30 days"
    }
  }'
```

## Running Workflows

### From the Admin UI

1. Navigate to **Workflows** in the sidebar.
2. Click **Test Workflow** on any template card.
3. Enter a prompt describing what you want the workflow to do.
4. Click **Execute**.
5. The execution appears in the **Execution History** table below.
6. Click any row to expand the detail panel showing step-by-step progress, output, and cost.

### From the API

```bash
# Get a JWT token
TOKEN=$(curl -s http://localhost:8086/auth/login \
  -H "Content-Type: application/json" \
  -d '{"api_key": "$LITELLM_KEY"}' | jq -r '.access_token')

# Execute a workflow
EXEC_ID=$(curl -s -X POST http://localhost:8086/api/v1/workflow-executions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_name": "Research Agent",
    "template": "research",
    "input_data": {"prompt": "Compare LLM pricing across major providers"}
  }' | jq -r '.execution_id')

# Poll for results
curl http://localhost:8086/api/v1/workflow-executions/$EXEC_ID \
  -H "Authorization: Bearer $TOKEN"
```

## Execution Lifecycle

Each execution progresses through these statuses:

| Status | Description |
|--------|-------------|
| `pending` | Execution created, waiting to start |
| `running` | Workflow is actively processing nodes |
| `completed` | All nodes finished successfully |
| `failed` | A node encountered an error |

### Execution Details

The execution detail response includes:

```json
{
  "execution_id": "exec-abc123",
  "workflow_name": "Research Agent",
  "status": "completed",
  "steps": [
    {
      "node": "parse_query",
      "status": "completed",
      "duration_ms": 1200,
      "cost": 0.002
    },
    {
      "node": "search_web",
      "status": "completed",
      "duration_ms": 3400,
      "cost": 0.008
    }
  ],
  "output": "## Research Report\n\n...",
  "total_tokens": 4521,
  "total_cost": 0.034,
  "duration_ms": 12400
}
```

## Custom Workflows

Create custom workflows by defining them through the API:

```bash
curl -X POST http://localhost:8086/api/v1/workflows \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Customer Support",
    "template": "research",
    "description": "Analyze customer tickets and generate response drafts",
    "config": {
      "model": "smart",
      "max_tokens": 2000
    },
    "is_active": true
  }'
```

Custom workflows appear alongside the pre-built templates in the Admin UI.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/workflows` | List all workflow definitions |
| POST | `/api/v1/workflows` | Create a custom workflow |
| PUT | `/api/v1/workflows/{id}` | Update a workflow |
| DELETE | `/api/v1/workflows/{id}` | Delete a workflow |
| POST | `/api/v1/workflow-executions` | Execute a workflow |
| GET | `/api/v1/workflow-executions` | List all executions |
| GET | `/api/v1/workflow-executions/{id}` | Get execution details |

## Temporal Dashboard

When the workflows profile is active, access the Temporal UI at **http://localhost:8088** to see:

- Running and completed workflow executions
- Workflow history and event timelines
- Worker status and task queues
- Retry and failure details

## Production Considerations

- **Model selection:** Workflow templates use the model specified in their config. Use group aliases (`smart`, `fast`) for automatic provider failover.
- **Cost awareness:** Multi-step workflows make several LLM calls. Monitor execution costs in the Execution History or Grafana FinOps dashboard.
- **Temporal persistence:** Temporal stores workflow state durably. If the workflow engine restarts mid-execution, it resumes from the last completed step.
- **Concurrency:** Temporal handles concurrent execution limits and rate limiting for workflow workers.

## Related Guides

- [Admin Guide](./admin-guide.md) -- Workflows page walkthrough
- [API Integration Guide](./api-integration.md) -- full API endpoint reference
- [Observability Guide](./observability.md) -- monitor workflow performance in Grafana
