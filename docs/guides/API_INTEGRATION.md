# API Integration Guide

The AI Control Plane exposes an OpenAI-compatible API on port 4000. Any application that works with the OpenAI API can connect to the gateway by changing the base URL and API key -- no other code changes required.

## Authentication

All requests to the gateway require a Bearer token in the `Authorization` header. Use the `LITELLM_MASTER_KEY` from your `config/.env` file:

```
Authorization: Bearer $LITELLM_KEY
```

For production, generate per-user or per-team API keys through the Admin UI or Admin API at `http://localhost:8086`.

## Base URL

| Environment | Base URL                                |
|-------------|----------------------------------------|
| Local       | `http://localhost:4000`                |
| Production  | `https://api.aicontrolplane.dev`       |
| Docs        | `https://docs.aicontrolplane.dev`      |
| Admin UI    | `https://api.aicontrolplane.dev/admin` |

All OpenAI-compatible endpoints live under `/v1/`:
- `POST /v1/chat/completions` -- chat completions (streaming and non-streaming)
- `POST /v1/embeddings` -- text embeddings
- `GET /v1/models` -- list available models

## Code Examples

### curl

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -d '{
    "model": "claude-sonnet-4.5",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "What is the capital of France?"}
    ],
    "max_tokens": 256,
    "temperature": 0.7
  }'
```

### Python (OpenAI SDK)

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:4000/v1",
    api_key="$LITELLM_KEY",
)

response = client.chat.completions.create(
    model="claude-sonnet-4.5",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is the capital of France?"},
    ],
    max_tokens=256,
    temperature=0.7,
)

print(response.choices[0].message.content)
```

### TypeScript (OpenAI SDK)

```typescript
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "http://localhost:4000/v1",
  apiKey: "$LITELLM_KEY",
});

const response = await client.chat.completions.create({
  model: "claude-sonnet-4.5",
  messages: [
    { role: "system", content: "You are a helpful assistant." },
    { role: "user", content: "What is the capital of France?" },
  ],
  max_tokens: 256,
  temperature: 0.7,
});

console.log(response.choices[0].message.content);
```

### Go (OpenAI SDK)

```go
package main

import (
    "context"
    "fmt"
    openai "github.com/sashabaranov/go-openai"
)

func main() {
    config := openai.DefaultConfig("$LITELLM_KEY")
    config.BaseURL = "http://localhost:4000/v1"

    client := openai.NewClientWithConfig(config)

    resp, err := client.CreateChatCompletion(
        context.Background(),
        openai.ChatCompletionRequest{
            Model: "claude-sonnet-4.5",
            Messages: []openai.ChatCompletionMessage{
                {Role: "system", Content: "You are a helpful assistant."},
                {Role: "user", Content: "What is the capital of France?"},
            },
            MaxTokens:   256,
            Temperature: 0.7,
        },
    )
    if err != nil {
        panic(err)
    }

    fmt.Println(resp.Choices[0].Message.Content)
}
```

## Model Aliases

Instead of specifying a provider-specific model, you can use group aliases that route across multiple providers automatically:

| Alias          | Routes to                                                 | Best for                     |
|----------------|----------------------------------------------------------|------------------------------|
| `fast`         | gpt-5-mini, claude-haiku-4.5, gemini-3-flash, grok-3-mini | Low-latency responses       |
| `smart`        | gpt-5, claude-sonnet-4.5, gemini-3-pro, grok-4            | Balanced quality & speed    |
| `powerful`     | gpt-5.2, claude-opus-4.5, o3-pro, grok-4-heavy            | Maximum capability          |
| `reasoning`    | o3, o3-pro, deepseek-r1                                    | Complex reasoning tasks     |
| `coding`       | claude-sonnet-4.5, deepseek-coder, codellama               | Code generation & review    |
| `cost-effective`| gpt-5-mini, claude-haiku-4.5, gemini-2.5-flash-lite, deepseek-v3 | Budget-friendly      |

```python
# Use a group alias -- the gateway picks the best available model
response = client.chat.completions.create(
    model="fast",
    messages=[{"role": "user", "content": "Summarize this text..."}],
)
```

Provider-specific aliases are also available: `openai`, `anthropic`, `google`, `xai`, `deepseek`, `bedrock`, `vertex`, `azure`.

## Streaming

Enable streaming by setting `stream: true`. The gateway returns Server-Sent Events (SSE) in the standard OpenAI format:

### Python Streaming

```python
stream = client.chat.completions.create(
    model="claude-sonnet-4.5",
    messages=[{"role": "user", "content": "Write a short poem about APIs."}],
    stream=True,
)

for chunk in stream:
    content = chunk.choices[0].delta.content
    if content:
        print(content, end="", flush=True)
```

### TypeScript Streaming

```typescript
const stream = await client.chat.completions.create({
  model: "claude-sonnet-4.5",
  messages: [{ role: "user", content: "Write a short poem." }],
  stream: true,
});

for await (const chunk of stream) {
  const content = chunk.choices[0]?.delta?.content;
  if (content) process.stdout.write(content);
}
```

## Embeddings

Generate text embeddings through the same gateway:

```python
response = client.embeddings.create(
    model="azure-text-embedding-3-large",
    input="The quick brown fox jumps over the lazy dog",
)

vector = response.data[0].embedding
print(f"Embedding dimension: {len(vector)}")
```

Available embedding models include `azure-text-embedding-3-large` and `azure-text-embedding-3-small`. These require `AZURE_API_KEY` and `AZURE_API_BASE` to be set in `config/.env`.

## Error Handling

The gateway returns standard HTTP error codes with JSON bodies:

| Status | Meaning                          | Common cause                              |
|--------|----------------------------------|------------------------------------------|
| 400    | Bad Request                      | Invalid JSON or missing required fields  |
| 401    | Unauthorized                     | Missing or invalid API key               |
| 404    | Not Found                        | Unknown model name                       |
| 429    | Rate Limited                     | Too many requests (RPM/TPM exceeded)     |
| 500    | Internal Server Error            | Upstream provider failure                |
| 503    | Service Unavailable              | All providers in fallback chain failed   |

### Python Error Handling

```python
from openai import OpenAI, APIError, RateLimitError, APIConnectionError

client = OpenAI(
    base_url="http://localhost:4000/v1",
    api_key="$LITELLM_KEY",
)

try:
    response = client.chat.completions.create(
        model="gpt-5",
        messages=[{"role": "user", "content": "Hello"}],
    )
except RateLimitError:
    print("Rate limited -- back off and retry")
except APIError as e:
    print(f"API error {e.status_code}: {e.message}")
except APIConnectionError:
    print("Could not connect to the gateway")
```

## Rate Limits

The gateway enforces rate limits at multiple levels:

- **Global**: 1000 requests/minute (configurable in Admin UI > Settings)
- **Per key**: 100 RPM and 100,000 TPM by default (configurable per API key)
- **Per model**: Provider-specific limits are respected automatically

When rate limited, the response includes a `Retry-After` header. The OpenAI SDKs handle this automatically with exponential backoff.

## Fallback Chains

When a primary model is unavailable or returns an error, the gateway automatically tries fallback models. For example, a request to `gpt-5` will fall back to `gpt-5.2`, then `claude-opus-4.5`, then `grok-4`.

Fallback happens transparently -- your application receives a response without needing to implement retry logic. The response metadata includes the actual model used:

```python
response = client.chat.completions.create(
    model="gpt-5",
    messages=[{"role": "user", "content": "Hello"}],
)

# Check which model actually served the request
print(response.model)  # Could be "gpt-5" or a fallback like "claude-opus-4.5"
```

Key fallback chains configured by default:

| Primary Model      | Fallback Sequence                            |
|--------------------|--------------------------------------------|
| gpt-5              | gpt-5.2, claude-opus-4.5, grok-4           |
| claude-opus-4.5    | claude-sonnet-4.5, gpt-5, grok-4           |
| claude-sonnet-4.5  | claude-opus-4.5, gpt-5, gemini-3-pro       |
| gemini-3-pro       | gemini-2.5-pro, claude-sonnet-4.5, gpt-5   |
| deepseek-r1        | o3, deepseek-v3                             |

## Admin API

The Admin API at `http://localhost:8086` (production: `https://api.aicontrolplane.dev/admin/api/v1`) provides management endpoints for programmatic configuration. It uses JWT authentication:

```bash
# Get a JWT token
TOKEN=$(curl -s http://localhost:8086/auth/login \
  -H "Content-Type: application/json" \
  -d '{"api_key": "$LITELLM_KEY"}' | jq -r '.access_token')
```

### Available Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/models` | List all model configurations |
| PUT | `/api/v1/models/{model_id}` | Update a model configuration |
| GET | `/api/v1/budgets` | List all budgets |
| POST | `/api/v1/budgets` | Create a budget |
| PUT | `/api/v1/budgets/{id}` | Update a budget |
| GET | `/api/v1/teams` | List all teams |
| POST | `/api/v1/teams` | Create a team |
| PUT | `/api/v1/teams/{team_id}` | Update a team |
| DELETE | `/api/v1/teams/{team_id}` | Delete a team |
| GET | `/api/v1/guardrail-assignments` | List guardrail-to-team assignments |
| GET | `/api/v1/keys` | List all API keys |
| POST | `/api/v1/keys/generate` | Generate a new API key |
| POST | `/api/v1/keys/update` | Update an API key |
| POST | `/api/v1/keys/delete` | Delete API keys |
| GET | `/api/v1/mcp-servers` | List MCP server configs |
| POST | `/api/v1/mcp-servers` | Create an MCP server config |
| PUT | `/api/v1/mcp-servers/{id}` | Update an MCP server config |
| POST | `/api/v1/mcp-servers/{id}/test` | Test MCP server connectivity |
| GET | `/api/v1/mcp-servers/sync/preview` | Preview Agent Gateway config |
| POST | `/api/v1/mcp-servers/sync` | Deploy MCP configs to Agent Gateway |
| GET | `/api/v1/workflows` | List workflow definitions |
| POST | `/api/v1/workflows` | Create a workflow |
| POST | `/api/v1/workflow-executions` | Execute a workflow |
| GET | `/api/v1/workflow-executions` | List workflow executions |
| GET | `/api/v1/workflow-executions/{id}` | Get execution details |
| GET | `/api/v1/routing-policies` | List routing policies |
| POST | `/api/v1/routing-policies` | Create a routing policy |
| GET | `/api/v1/metrics/realtime` | Get real-time platform metrics |
| GET | `/api/v1/settings` | Get platform settings |
| PUT | `/api/v1/settings` | Update platform settings |

```bash
# Example: List models
curl http://localhost:8086/api/v1/models \
  -H "Authorization: Bearer $TOKEN"

# Example: Generate an API key
curl -X POST http://localhost:8086/api/v1/keys/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"key_alias": "my-service", "max_budget": 100, "duration": "90d"}'

# Example: Preview Agent Gateway config
curl http://localhost:8086/api/v1/mcp-servers/sync/preview \
  -H "Authorization: Bearer $TOKEN"
```

See the [Admin UI Guide](./ADMIN_GUIDE.md) for the full web console walkthrough.
