# k6 Load Tests

Load and stress tests for the AI Control Plane platform services.

## Test Files

| File | Target Service | Description |
|------|---------------|-------------|
| `load_test.js` | LiteLLM proxy (`:4000`) | Sustained load against `/v1/chat/completions` with multiple models |
| `stress_test.js` | LiteLLM proxy (`:4000`) | Ramps VUs to 500 to find the breaking point of the LLM proxy |
| `platform_test.js` | Admin API (`:8086`) | Authenticated load test across all admin endpoints (models, budgets, teams, metrics, settings) |
| `cache_test.js` | Semantic Cache (`:8083`) | Cache lookup/store patterns with synthetic prompts and tag-filtered vector search |

## Prerequisites

- [k6](https://k6.io/docs/get-started/installation/) installed locally
- Target services running (see required services per test below)

## Running Tests

```bash
# LLM proxy load test (requires: litellm, postgres, redis)
k6 run tests/load/k6/load_test.js

# Platform services load test (requires: admin-api, postgres)
k6 run tests/load/k6/platform_test.js

# Semantic cache load test (requires: semantic-cache, redis, litellm for embeddings)
k6 run tests/load/k6/cache_test.js

# Stress test — find breaking point (requires: litellm, postgres, redis)
k6 run tests/load/k6/stress_test.js
```

## Custom VUs and Duration

Override the built-in stages with explicit VU count and duration:

```bash
k6 run --vus 50 --duration 5m tests/load/k6/platform_test.js
k6 run --vus 100 --duration 10m tests/load/k6/cache_test.js
```

## Environment Variables

All tests accept configuration via environment variables using `k6 run -e KEY=VALUE`:

### load_test.js / stress_test.js

| Variable | Default | Description |
|----------|---------|-------------|
| `LITELLM_URL` | `http://localhost:4000` | LiteLLM proxy base URL |
| `API_KEY` | `sk-test-key` | LiteLLM API key for authentication |

### platform_test.js

| Variable | Default | Description |
|----------|---------|-------------|
| `ADMIN_API_URL` | `http://localhost:8086` | Admin API base URL |
| `API_KEY` | `$LITELLM_KEY` | LiteLLM master key (used to obtain JWT) |

### cache_test.js

| Variable | Default | Description |
|----------|---------|-------------|
| `CACHE_URL` | `http://localhost:8083` | Semantic Cache base URL |
| `SERVICE_KEY` | _(empty)_ | Inter-service auth key (`X-Service-Key` header) |
| `LITELLM_KEY` | _(empty)_ | LiteLLM API key for embedding generation |

## Examples

```bash
# Test admin API on a remote host
k6 run -e ADMIN_API_URL=https://gateway.example.com:8086 \
       -e API_KEY=sk-my-production-key \
       tests/load/k6/platform_test.js

# Test semantic cache with service auth
k6 run -e CACHE_URL=http://localhost:8083 \
       -e SERVICE_KEY=my-internal-key \
       -e LITELLM_KEY=$LITELLM_KEY \
       tests/load/k6/cache_test.js

# Output results to JSON for post-processing
k6 run --out json=results.json tests/load/k6/platform_test.js

# Output to InfluxDB for Grafana dashboards
k6 run --out influxdb=http://localhost:8086/k6 tests/load/k6/load_test.js
```

## Thresholds

Each test defines pass/fail thresholds. k6 exits with a non-zero code if any threshold is breached, making these tests suitable for CI/CD gates.

### platform_test.js

- All admin endpoints P95 < 500ms
- Health check P99 < 100ms
- Error rate < 1% (per endpoint and global)

### cache_test.js

- Cache lookup P95 < 200ms (hot path)
- Cache store P95 < 500ms
- Stats/health P95 < 300ms, P99 < 100ms
- Error rate < 1% (per endpoint and global)

### load_test.js

- Chat completions P95 < 2s
- Error rate < 1%

### stress_test.js

- Chat completions P99 < 5s
- Error rate < 10% (lenient — stress test finds breaking point)
