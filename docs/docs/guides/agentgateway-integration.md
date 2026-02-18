# Agent Gateway Integration

How the AI Control Plane uses Agent Gateway, which features are pre-configured, and which are available for adoption.

## Our Approach

Agent Gateway v0.12+ is a powerful standalone product with MCP federation, A2A routing, LLM proxying, CEL authorization, prompt guards, and more. Most users only configure basic MCP stdio targets because the feature surface is large and documentation assumes deep familiarity.

This platform **makes Agent Gateway manageable** by storing config in a database, providing a UI for CRUD operations, and deploying config changes atomically.

### The Config Sync Pipeline

```
Admin UI
    ↓ (create/update/delete MCP server or A2A agent)
Admin API
    ↓ (write to database)
PostgreSQL (source of truth)
    ↓ (gateway_sync.py)
config.yaml (shared Docker volume)
    ↓ (file watcher detects change)
Agent Gateway (hot-reload — zero downtime)
```

This pipeline means:
- **No manual YAML editing** — all changes through the UI
- **Config survives restarts** — Postgres is the source of truth, config regenerated on startup
- **Atomic deploys** — MCP servers and A2A agents deployed together
- **Audit trail** — who created what, with timestamps

### What We Pre-Configure

| Feature | Config | Platform Value-Add |
|---------|--------|--------------------|
| **MCP federation** | `backends.mcp.targets` | DB-backed CRUD via Admin UI, test connectivity, deploy with one click |
| **A2A backends** | `backends.a2a.targets` | DB-backed CRUD via Admin UI, test connectivity, deploy alongside MCP |
| **CORS** | `policies.cors` | Pre-configured for browser-based MCP clients |
| **Session management** | `Mcp-Session-Id` header | Exposed for stateful tool interactions |
| **Docker networking** | Container config | Connected to platform network, depends on Postgres/LiteLLM health |
| **OTEL integration** | Environment variables | Traces flow to platform's OTEL collector → Jaeger |

### What the Admin UI Exposes

| Admin UI Page | What You Can Do |
|---------------|-----------------|
| **MCP Servers** | Add/edit/delete MCP servers (name, type, command/URL, args, env). Test connectivity. Toggle active/inactive. Preview generated config YAML. Deploy to gateway. |
| **A2A Agents** | Add/edit/delete A2A agents (name, description, URL, skills). Test connectivity. Toggle active/inactive. Deploy to gateway. |
| **Config Preview** | See the exact YAML that will be written to the gateway — both MCP and A2A sections |
| **Deploy to Gateway** | Push all active MCP servers + A2A agents to the shared volume in one operation |

---

## Agent Gateway Features We Surface

### MCP Server Management

Instead of editing YAML, operators use the Admin UI:

```
# Without the platform:
vim config/agentgateway/config.yaml
# Add target, hope the YAML is valid
docker compose restart agentgateway

# With the platform:
# Click "Add Server" → fill form → "Test" → "Deploy to Gateway"
# Hot-reload, no restart needed
```

Supported server types:
- **stdio** — subprocess-based (npx, uvx, python commands)
- **http** — remote MCP servers via SSE

### A2A Agent Management

Same UI-driven workflow for A2A agents:

- Add agents with name, description, URL, and skills tags
- Test connectivity before deploying
- Toggle active/inactive without deleting
- Deploy alongside MCP servers atomically

### Observability

Agent Gateway emits OTEL traces and Prometheus metrics. Pre-wired in the platform:

- **Traces** → OTEL Collector → Jaeger (visible at localhost:16686)
- **Metrics** → Prometheus → Grafana dashboards

Metrics include: token usage, request latency, time-to-first-token, per-provider/model breakdowns.

---

## Features Available for Adoption

Agent Gateway has many capabilities beyond what the platform currently uses. These are ready to enable:

### High-Impact, Easy to Enable

| Feature | Effort | Value |
|---------|--------|-------|
| **SSE/StreamableHTTP transports** | Add to MCP server config | Connect to remote MCP servers over HTTP, not just local stdio |
| **OpenAPI-to-MCP bridge** | Config change | Turn any REST API into MCP tools automatically — no custom MCP server needed |
| **Built-in admin UI** | Already exposed at port 15000 | CEL playground, backend management, tool testing |
| **Prompt guards** | Policy config | Block requests with credit cards, PII, or prompt injection attempts |
| **Tool poisoning protection** | Policy config | Detect malicious tool descriptions that could manipulate agents |

### Medium-Impact, Moderate Effort

| Feature | Effort | Value |
|---------|--------|-------|
| **CEL authorization** | Policy config | Per-tool access control (e.g., only admins can use `write_file`) |
| **JWT authentication** | Policy config | Validate JWT tokens on MCP/A2A connections |
| **OAuth 2.0 for MCP** | Policy config + auth server | RFC 9728-compliant OAuth for MCP clients |
| **Local rate limiting** | Policy config | Token-bucket rate limiting per MCP endpoint |
| **LLM gateway mode** | Backend config | Use Agent Gateway as LLM proxy (alternative to LiteLLM for some use cases) |
| **Request/response transformation** | CEL expressions | Modify tool inputs/outputs at the gateway level |

### Advanced / Kubernetes

| Feature | Effort | Value |
|---------|--------|-------|
| **xDS dynamic configuration** | kgateway control plane | Zero-downtime config updates via xDS protocol (like Envoy) |
| **Gateway API CRDs** | Kubernetes manifests | `AgentgatewayPolicy`, `AgentgatewayBackend` custom resources |
| **mTLS / HBONE** | TLS config | Mutual TLS for service mesh integration |
| **ExtAuthz** | Policy config | Delegate auth to external services (Auth0, Keycloak, Tailscale) |
| **Distributed rate limiting** | Redis + policy config | Shared rate limit state across multiple gateway instances |
| **Global rate limiting** | Redis backend | Hierarchical descriptor matching for complex rate limit rules |

---

## Architecture Details

### Generated Config Format

When you deploy from the Admin UI, `gateway_sync.py` generates this structure:

```yaml
binds:
  - port: 3000
    listeners:
      - routes:
          - policies:
              cors:
                allowOrigins: ["*"]
                allowHeaders:
                  - mcp-protocol-version
                  - content-type
                  - authorization
                  - accept
                exposeHeaders:
                  - Mcp-Session-Id
            backends:
              - mcp:
                  targets:
                    - name: filesystem
                      stdio:
                        cmd: npx
                        args: ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"]
                    - name: my-api
                      sse:
                        url: "http://my-mcp-server:3001"
              - a2a:
                  targets:
                    - name: code-reviewer
                      url: "http://code-review-agent:8088"
                    - name: test-runner
                      url: "http://test-agent:8089"
```

### Docker Compose Setup

```yaml
agentgateway:
  build: ./config/agentgateway/Dockerfile
  profiles: ["full"]
  ports:
    - "9000:3000"    # MCP/A2A endpoint
    - "15000:15000"  # Built-in admin UI
    - "15020:15020"  # Health/readiness probes
  volumes:
    - gateway-config:/app/gateway-config  # Shared with admin-api
  environment:
    OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4318
```

### Startup Sync

On `admin-api` startup, `_sync_gateway_config_on_startup()` reads all active MCP servers and A2A agents from Postgres and writes `config.yaml` to the shared volume. This ensures the gateway has a valid config even after a fresh deployment.

---

## Migration from Standalone Agent Gateway

### Step 1: Import Your MCP Targets

For each target in your existing `config.yaml`, create it in the Admin UI:

1. Open Admin UI → MCP Servers → Add Server
2. Enter name, type (stdio/http), command/URL, args
3. Test connectivity
4. Repeat for all targets

### Step 2: Import A2A Agents

1. Open Admin UI → A2A Agents → Add Agent
2. Enter name, description, URL, skills
3. Test connectivity

### Step 3: Deploy

Click "Deploy to Gateway" — both MCP and A2A targets are written to the gateway config atomically.

### Step 4: Migrate Policies

If you used CEL policies, you have two options:

- **Keep CEL in Agent Gateway** — add policies to the generated config manually (the platform doesn't manage policies via UI yet)
- **Use LiteLLM guardrails** — for content-level guardrails, configure via Admin UI Guardrails page

### Keeping Non-Platform Features

Features like CEL authorization, OAuth 2.0, rate limiting, and prompt guards can be added by extending the config template in `gateway_sync.py`. The generated config is standard Agent Gateway YAML — you can add any policy section.

---

## Integrating with an Existing Agent Gateway Instance

If you already run Agent Gateway in production (standalone or via kgateway), you can connect the platform to it instead of using the bundled instance. The Admin UI becomes a config management layer that pushes changes to your existing gateway.

### How Config Sync Works with External Instances

The platform supports two sync methods:

| Method | Environment Variable | When to Use |
|--------|---------------------|-------------|
| **Shared volume / file path** | `GATEWAY_CONFIG_PATH` | Docker Compose, same host |
| **Kubernetes ConfigMap** | `GATEWAY_CONFIGMAP_NAME`, `GATEWAY_DEPLOYMENT_NAME` | Kubernetes, separate namespace |

When you create or update MCP servers and A2A agents in the Admin UI and click "Deploy to Gateway", `gateway_sync.py` writes the config to your gateway via the configured method.

### Option A: File-Based Sync (Docker Compose / Same Host)

If your Agent Gateway reads config from a file and supports hot-reload (file watcher):

#### Step 1: Mount the Same Config Path

In `docker-compose.override.yaml`:

```yaml
services:
  agentgateway:
    profiles: ["disabled"]  # Don't start the bundled gateway

  admin-api:
    environment:
      GATEWAY_CONFIG_PATH: /app/gateway-config/config.yaml
    volumes:
      - /path/to/your/gateway/config:/app/gateway-config
```

Replace `/path/to/your/gateway/config` with the directory your existing Agent Gateway reads its `config.yaml` from.

#### Step 2: Verify

```bash
# Deploy from Admin UI, then check the file was written
cat /path/to/your/gateway/config/config.yaml

# Your gateway's file watcher picks up the change automatically
```

### Option B: Kubernetes ConfigMap Sync

If your Agent Gateway runs in Kubernetes and reads config from a ConfigMap:

#### Step 1: Configure the Admin API

Set these environment variables on the Admin API deployment:

```yaml
# In your Admin API Kubernetes manifest or Helm values
env:
  - name: GATEWAY_CONFIGMAP_NAME
    value: "your-agentgateway-configmap"   # Default: agentgateway-config
  - name: GATEWAY_DEPLOYMENT_NAME
    value: "your-agentgateway-deployment"  # Default: agentgateway
  - name: K8S_NAMESPACE
    value: "your-gateway-namespace"        # Default: auto-detected from service account
```

#### Step 2: Grant RBAC Permissions

The Admin API's service account needs permission to patch the ConfigMap and trigger a rolling restart:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: admin-api-gateway-sync
  namespace: your-gateway-namespace
rules:
  - apiGroups: [""]
    resources: ["configmaps"]
    resourceNames: ["your-agentgateway-configmap"]
    verbs: ["get", "patch"]
  - apiGroups: ["apps"]
    resources: ["deployments"]
    resourceNames: ["your-agentgateway-deployment"]
    verbs: ["get", "patch"]
```

#### Step 3: Deploy and Verify

When you click "Deploy to Gateway" in the Admin UI, the platform:

1. Reads all active MCP servers and A2A agents from Postgres
2. Generates a `config.yaml`
3. PATCHes the ConfigMap with the new config
4. Triggers a rolling restart by annotating the Deployment with `admin-api/restartedAt`

```bash
# Verify the ConfigMap was updated
kubectl get configmap your-agentgateway-configmap -n your-gateway-namespace -o yaml
```

### What Works

| Feature | Status | Notes |
|---------|--------|-------|
| MCP server CRUD | Works | Config stored in Postgres, deployed to your gateway |
| A2A agent CRUD | Works | Same pipeline as MCP servers |
| Connectivity testing | Works | Admin API tests reachability of MCP/A2A targets directly |
| Config preview | Works | Shows generated YAML before deploying |
| Deploy to gateway | Works | Writes via file or ConfigMap, depending on config |
| Gateway admin UI | Independent | Your gateway's built-in UI at port 15000 still works separately |

### What Does Not Work

- **Policy management**: The platform generates the `backends` section of the config but does not manage CEL policies, auth config, rate limiting, or other policy sections. These must be configured in your existing gateway setup.
- **OTEL integration**: If your gateway already sends traces to a different collector, the platform's Jaeger/Grafana won't show Agent Gateway traces unless you reconfigure the exporter endpoint.

### Preserving Your Existing Config

The platform only manages the `backends` section (MCP targets + A2A targets) and CORS policies. If your existing config has additional sections (authentication, rate limiting, CEL policies), you can extend `gateway_sync.py`'s `build_gateway_config()` function to merge them:

```python
# In gateway_sync.py, after generating the base config:
# Load your existing policy sections and merge them into the generated config
```

Alternatively, use Agent Gateway's support for multiple config sources — load the platform-generated config for backends and a separate file for policies.

---

## Related Guides

- [Comparison](./comparison.md) — how the platform compares to alternatives
- [LiteLLM Deep Dive](./litellm-integration.md) — LiteLLM features and integration
- [Cost Management](./cost-management.md) — budgets and FinOps
- [Admin Guide](./admin-guide.md) — UI walkthrough
