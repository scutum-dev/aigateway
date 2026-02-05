# Cloud Deployment Guide

Single-command deployment to GCP using Terraform + Makefile.

## Quick Start

```bash
# Deploy demo environment
make demo

# Destroy when done
make demo-destroy
```

## Prerequisites

1. **GCP Project** with billing enabled
2. **CLI Tools:**
   ```bash
   # Authenticate with GCP
   gcloud auth application-default login

   # Verify tools
   terraform --version   # >= 1.0
   kubectl version       # >= 1.25
   docker --version      # >= 20.0
   ```

3. **Required GCP APIs** (enabled automatically by Terraform):
   - Kubernetes Engine API
   - Artifact Registry API
   - Compute Engine API
   - Cloud Resource Manager API
   - Cloud Billing Budget API

## Environments

| Environment | Command | Replicas | Features |
|-------------|---------|----------|----------|
| **Demo** | `make demo` | 1 | Quick teardown, seeded data, no deletion protection |
| **Staging** | `make staging` | 2 | Pre-prod testing |
| **Production** | `make prod` | 3+ | Deletion protection, HA, confirmation required |

## Configuration

### Environment Variables (tfvars)

Each environment has a configuration file in `terraform/environments/`:

```
terraform/environments/
├── main.tf           # Shared infrastructure
├── variables.tf      # Variable definitions
├── outputs.tf        # Outputs
├── backend.tf        # GCS backend
├── demo.tfvars       # Demo configuration
├── staging.tfvars    # Staging configuration
└── prod.tfvars       # Production configuration
```

### Required Variables

Create your tfvars file based on `demo.tfvars`:

```hcl
# GCP Configuration
project_id = "your-gcp-project"
region     = "asia-south1"

# Domain Configuration
domain            = "yourdomain.com"
subdomain         = "gateway"
letsencrypt_email = "admin@yourdomain.com"

# API Keys (use environment variables or Vault in production)
openai_api_key    = ""  # Or set via TF_VAR_openai_api_key
anthropic_api_key = ""
xai_api_key       = ""

# Gateway Configuration
litellm_master_key = "sk-your-secure-key"
grafana_password   = "secure-password"

# Scaling
replicas         = 1
min_replicas     = 1
max_replicas     = 3

# Safety
deletion_protection = false  # true for production
```

### Sensitive Values

**Never commit API keys to Git.** Use one of these approaches:

1. **Environment Variables:**
   ```bash
   export TF_VAR_openai_api_key="sk-..."
   export TF_VAR_anthropic_api_key="sk-ant-..."
   make demo
   ```

2. **Separate secrets file (gitignored):**
   ```bash
   # terraform/environments/secrets.auto.tfvars (add to .gitignore)
   openai_api_key    = "sk-..."
   anthropic_api_key = "sk-ant-..."
   ```

3. **GCP Secret Manager** (recommended for production)

## Deployment Workflow

The `make demo` command executes this workflow:

```
┌─────────────────────────────────────────────────────────────────┐
│                        make demo                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. _infra: Terraform Apply                                       │
│    • GKE Autopilot cluster                                       │
│    • VPC + Cloud NAT (for private nodes)                         │
│    • Artifact Registry                                           │
│    • Helm releases (nginx-ingress, cert-manager)                 │
│    • Kubernetes namespace + secrets                              │
│    • Kustomize apply (LiteLLM, PostgreSQL, Redis, etc.)         │
│    • Ingress + TLS certificate                                   │
│    • Route53 DNS record                                          │
│    • GCP Budget alert                                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. _build: Docker Build & Push                                   │
│    • Build admin-api (linux/amd64 for GKE)                       │
│    • Build admin-ui (linux/amd64 for GKE)                        │
│    • Push to Artifact Registry                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. _wait: Wait for Services                                      │
│    • Restart deployments to pick up new images                   │
│    • Wait for PostgreSQL, Redis, LiteLLM, Admin API              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. _seed: Seed Demo Data (non-prod only)                         │
│    • Create demo models, budgets, teams                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. _output: Show URLs & Credentials                              │
└─────────────────────────────────────────────────────────────────┘
```

## Access URLs

After deployment, run `make cloud-output` to see:

```
urls = {
  "admin_api" = "https://gateway.yourdomain.com/admin-api"
  "admin_ui"  = "https://gateway.yourdomain.com/admin"
  "api_docs"  = "https://gateway.yourdomain.com/docs"
  "gateway"   = "https://gateway.yourdomain.com"
  "grafana"   = "https://gateway.yourdomain.com/grafana"
  "health"    = "https://gateway.yourdomain.com/health/readiness"
}
```

## Commands Reference

| Command | Description |
|---------|-------------|
| `make demo` | Deploy demo environment |
| `make staging` | Deploy staging environment |
| `make prod` | Deploy production (requires confirmation) |
| `make demo-destroy` | Destroy demo environment |
| `make staging-destroy` | Destroy staging environment |
| `make prod-destroy` | Destroy production (requires confirmation) |
| `make cloud-status` | Show Terraform state |
| `make cloud-output` | Show deployment outputs |
| `make cloud-plan` | Preview Terraform changes |

## Architecture

```
                                    Internet
                                        │
                                        ▼
                              ┌─────────────────┐
                              │   Cloud DNS     │
                              │  (Route53/GCP)  │
                              └────────┬────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                            GKE Autopilot                                  │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                     nginx-ingress-controller                        │  │
│  │                        (LoadBalancer)                               │  │
│  └───────────┬──────────────┬──────────────┬──────────────┬───────────┘  │
│              │              │              │              │               │
│      /v1/*   │    /admin/*  │  /admin-api/*│   /grafana/* │               │
│              ▼              ▼              ▼              ▼               │
│  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌──────────────┐  │
│  │   LiteLLM     │ │   Admin UI    │ │   Admin API   │ │   Grafana    │  │
│  │   (Proxy)     │ │   (React)     │ │   (FastAPI)   │ │              │  │
│  └───────┬───────┘ └───────────────┘ └───────┬───────┘ └──────┬───────┘  │
│          │                                   │                │          │
│          └──────────────────┬────────────────┘                │          │
│                             ▼                                 ▼          │
│                    ┌─────────────────┐              ┌─────────────────┐  │
│                    │   PostgreSQL    │              │   Prometheus    │  │
│                    └─────────────────┘              └─────────────────┘  │
│                    ┌─────────────────┐                                   │
│                    │     Redis       │                                   │
│                    └─────────────────┘                                   │
└──────────────────────────────────────────────────────────────────────────┘
```

## Troubleshooting

### Terraform Timeout

GKE Autopilot can take 10-15 minutes for initial node provisioning:
```bash
# Helm timeouts are set to 600s, increase if needed in main.tf
```

### Images Not Updating

Force restart deployments:
```bash
NAMESPACE=$(cd terraform/environments && terraform output -raw namespace)
kubectl -n $NAMESPACE rollout restart deployment/litellm
kubectl -n $NAMESPACE rollout restart deployment/admin-api
```

### Check Pod Status

```bash
NAMESPACE=$(cd terraform/environments && terraform output -raw namespace)
kubectl -n $NAMESPACE get pods
kubectl -n $NAMESPACE describe pod <pod-name>
kubectl -n $NAMESPACE logs <pod-name>
```

### Certificate Issues

Wait for cert-manager to issue certificates:
```bash
kubectl get certificates -A
kubectl describe certificate -n $NAMESPACE
```

### Connect to Cluster

```bash
gcloud container clusters get-credentials gateway-demo \
  --region asia-south1 \
  --project your-project-id
```

## Cost Management

A GCP budget alert is automatically created:
- Amount: INR 2000 (configurable via `budget_amount`)
- Thresholds: 50%, 80%, 100%
- Email alerts to configured address

To destroy and stop costs:
```bash
make demo-destroy
```
