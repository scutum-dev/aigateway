# Load tests

Two harnesses, same idea — pick whichever you have installed.

## Locust (`locustfile.py`)

```bash
# Quick mixed-workload smoke (30s, 30 users)
locust -f tests/load/locustfile.py --headless -u 30 -r 5 -t 30s --host http://localhost

# Hammer just the LLM proxy
locust -f tests/load/locustfile.py LiteLLMUser --headless -u 100 -r 10 -t 1m \
  --host http://localhost:4000

# Browser UI (open http://localhost:8089)
locust -f tests/load/locustfile.py
```

### What gets exercised

| User class | Surface | Key endpoints |
|---|---|---|
| `LiteLLMUser` | LiteLLM proxy `:4000` | `/health/liveliness`, `/v1/models`, `/model/info` |
| `AdminAPIUser` | Admin API `:8086` | JWT login, `/leads`, `/sre/incidents`, `/models`, `/reports/summary`, `/audit-logs` |
| `LandingUser` | Public landing `:9999` | `/`, `/api/demo-availability`, `POST /api/demo-request` |

### What's deliberately NOT tested by default

- `/v1/chat/completions` — real LLM calls cost money and measure the upstream
  provider's latency, not your platform. Uncomment the task in `LiteLLMUser` to
  enable, ideally pointed at a local mock model.

### Reading the results

The platform's bottleneck moves predictably as you scale users:

1. **<50 users**: everything green. Median latency ~5-50ms, no errors.
2. **50–200 users**: Postgres connection pool starts to saturate first (admin-api uses min=2, max=10). Watch for queueing on `/leads`, `/sre/incidents`. Increase `min_size`/`max_size` in the asyncpg pool if you see queueing here.
3. **200–500 users**: LiteLLM's internal worker count caps. Check container CPU and tune the LiteLLM worker config.
4. **>500 users**: nginx (landing-ui) and Docker Desktop's networking become the bottleneck on a single laptop. Real numbers require a multi-node deploy.

Useful flags:

- `--html /tmp/load.html` — full HTML report
- `--csv /tmp/load` — CSV per-endpoint and overall
- `--stop-timeout 5` — graceful shutdown window

## k6 (`k6/`)

The pre-existing k6 tests live in `k6/`. Run with `k6 run tests/load/k6/load_test.js`. They're more comprehensive but require k6 binary installed.
