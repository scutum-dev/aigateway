# Production Readiness Checklist

This checklist ensures all components are properly configured for production deployment.

## Pre-Deployment Checklist

### 1. Secrets Management

| Item | Status | Notes |
|------|--------|-------|
| [ ] Replace `$LITELLM_KEY` with secure random key | Required | Use `openssl rand -hex 32` |
| [ ] Configure Vault with production token (not `root-token-for-dev`) | Required | Enable AppRole auth |
| [ ] Add real API keys to Vault | Required | OpenAI, Anthropic, XAI keys |
| [ ] Set `BRAVE_API_KEY` if using Brave Search MCP | Optional | Get from brave.com |
| [ ] Set `GITHUB_TOKEN` if using GitHub MCP | Optional | Create fine-grained PAT |
| [ ] Enable Vault audit logging | Required | Compliance requirement |
| [ ] Configure secret rotation policy | Recommended | 90-day rotation |

### 2. Database Configuration

| Item | Status | Notes |
|------|--------|-------|
| [ ] Use production PostgreSQL (not container) | Required | RDS, Cloud SQL, or managed |
| [ ] Configure SSL/TLS for database connections | Required | `sslmode=require` |
| [ ] Set up database backups | Required | Daily automated backups |
| [ ] Configure connection pooling | Recommended | PgBouncer or built-in |
| [ ] Create separate database users per service | Recommended | Principle of least privilege |
| [ ] Set appropriate resource limits | Required | Based on load testing |

### 3. TLS/SSL Configuration

| Item | Status | Notes |
|------|--------|-------|
| [ ] Install cert-manager | Required | For automatic certificate management |
| [ ] Configure ClusterIssuer for Let's Encrypt | Required | Use `letsencrypt-prod` |
| [ ] Update ingress hosts with real domain names | Required | Replace `example.com` |
| [ ] Configure TLS 1.2+ only | Required | Disable TLS 1.0/1.1 |
| [ ] Enable HSTS | Recommended | `Strict-Transport-Security` header |

### 4. Authentication & Authorization

| Item | Status | Notes |
|------|--------|-------|
| [ ] Configure OIDC/OAuth provider | Required | For admin UI access |
| [ ] Set up API key management | Required | Virtual keys in LiteLLM |
| [ ] Review Cedar RBAC policies | Required | `config/agentgateway/policies/` |
| [ ] Configure JWT validation | Required | For A2A authentication |
| [ ] Set rate limits per user/team | Recommended | Prevent abuse |

### 5. Network Security

| Item | Status | Notes |
|------|--------|-------|
| [ ] Review NetworkPolicy rules | Required | Least privilege |
| [ ] Configure WAF rules | Recommended | AWS WAF, Cloudflare |
| [ ] Set up DDoS protection | Recommended | Cloud provider DDoS |
| [ ] Whitelist admin endpoints | Required | IP-based or VPN only |
| [ ] Configure egress rules | Recommended | Restrict outbound traffic |

### 6. Observability

| Item | Status | Notes |
|------|--------|-------|
| [ ] Configure Prometheus retention | Required | Based on storage budget |
| [ ] Set up alerting rules | Required | 35 rules in `prometheus/alerts/` |
| [ ] Configure PagerDuty/Opsgenie integration | Required | For on-call |
| [ ] Review Grafana dashboards | Recommended | Customize for your needs |
| [ ] Configure log aggregation | Required | Loki, CloudWatch, or Datadog |
| [ ] Set up trace sampling | Recommended | 10-20% in production |

### 7. Resource Sizing

| Item | Status | Notes |
|------|--------|-------|
| [ ] Configure HPA min/max replicas | Required | Based on traffic patterns |
| [ ] Set appropriate resource requests/limits | Required | See sizing guide below |
| [ ] Configure PDB (PodDisruptionBudget) | Required | `minAvailable: 1` |
| [ ] Set up node affinity rules | Recommended | Spread across AZs |
| [ ] Configure pod anti-affinity | Recommended | Prevent single-node failure |

### 8. High Availability

| Item | Status | Notes |
|------|--------|-------|
| [ ] Deploy across multiple AZs | Required | Minimum 2 AZs |
| [ ] Configure Redis HA (Sentinel/Cluster) | Recommended | For rate limiting |
| [ ] Set up PostgreSQL replicas | Required | Read replicas |
| [ ] Configure load balancer health checks | Required | `/health` endpoint |
| [ ] Test failover procedures | Required | Document in runbook |

---

## Resource Sizing Guide

### Small (< 100 req/sec)
```yaml
# LiteLLM
resources:
  requests:
    cpu: 500m
    memory: 512Mi
  limits:
    cpu: 2000m
    memory: 2Gi
replicas: 2

# Agent Gateway
resources:
  requests:
    cpu: 250m
    memory: 256Mi
  limits:
    cpu: 1000m
    memory: 1Gi
replicas: 2
```

### Medium (100-500 req/sec)
```yaml
# LiteLLM
resources:
  requests:
    cpu: 1000m
    memory: 1Gi
  limits:
    cpu: 4000m
    memory: 4Gi
replicas: 4

# Agent Gateway
resources:
  requests:
    cpu: 500m
    memory: 512Mi
  limits:
    cpu: 2000m
    memory: 2Gi
replicas: 4
```

### Large (500-2000 req/sec)
```yaml
# LiteLLM
resources:
  requests:
    cpu: 2000m
    memory: 2Gi
  limits:
    cpu: 8000m
    memory: 8Gi
replicas: 8

# Agent Gateway
resources:
  requests:
    cpu: 1000m
    memory: 1Gi
  limits:
    cpu: 4000m
    memory: 4Gi
replicas: 8
```

### Enterprise (> 2000 req/sec)
```yaml
# LiteLLM
resources:
  requests:
    cpu: 4000m
    memory: 4Gi
  limits:
    cpu: 16000m
    memory: 16Gi
replicas: 16

# Agent Gateway
resources:
  requests:
    cpu: 2000m
    memory: 2Gi
  limits:
    cpu: 8000m
    memory: 8Gi
replicas: 16
```

---

## Deployment Steps

### 1. Pre-flight Checks
```bash
# Verify Kubernetes cluster
kubectl cluster-info
kubectl get nodes

# Check required namespaces
kubectl get ns | grep -E "(agentgateway|litellm|observability|database)"

# Verify secrets are configured
kubectl get secrets -n litellm
kubectl get secrets -n agentgateway
```

### 2. Deploy Infrastructure
```bash
# Apply base manifests
kubectl apply -k kubernetes/base/

# Wait for database to be ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=postgresql -n database --timeout=300s

# Apply overlays for environment
kubectl apply -k kubernetes/overlays/production/
```

### 3. Verify Deployment
```bash
# Check all pods are running
kubectl get pods -A | grep -E "(agentgateway|litellm|prometheus|grafana)"

# Verify services
kubectl get svc -A | grep -E "(agentgateway|litellm)"

# Check ingress
kubectl get ingress -A

# Test health endpoints
curl -k https://api.example.com/health
curl -k https://api.example.com/v1/models
```

### 4. Run Smoke Tests
```bash
# Test LLM endpoint
curl -X POST https://api.example.com/v1/chat/completions \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "Hello"}]}'

# Test MCP endpoint
curl https://api.example.com/mcp/tools

# Check metrics
curl https://api.example.com/metrics | head -20
```

---

## Monitoring & Alerting

### Critical Alerts (Page Immediately)
- Service unavailable (5xx > 5% for 5 min)
- Database connection failures
- Certificate expiration (< 7 days)
- Memory usage > 90%
- Vault sealed

### Warning Alerts (Slack/Email)
- Latency P99 > 5s
- Error rate > 1%
- Budget utilization > 80%
- Disk usage > 80%
- Pod restarts > 3 in 1 hour

### Info Alerts (Dashboard Only)
- New model deployments
- Configuration changes
- Scaling events

---

## Backup & Recovery

### What to Backup
- PostgreSQL database (daily)
- Vault secrets (encrypted export)
- ConfigMaps and Secrets
- Prometheus metrics (optional)

### Recovery Procedures
1. **Database Recovery**: Restore from RDS/Cloud SQL snapshot
2. **Secrets Recovery**: Restore from Vault backup or re-create
3. **Full Cluster Recovery**: Apply manifests from Git + restore database

### RTO/RPO Targets
- RTO (Recovery Time Objective): 1 hour
- RPO (Recovery Point Objective): 1 hour (daily backups with WAL archiving)

---

## Security Hardening

### Container Security
- [x] Non-root user (`runAsNonRoot: true`)
- [x] Read-only root filesystem where possible
- [x] No privilege escalation (`allowPrivilegeEscalation: false`)
- [ ] Enable seccomp profiles
- [ ] Enable AppArmor/SELinux

### Network Security
- [x] NetworkPolicy for namespace isolation
- [x] TLS for all external traffic
- [ ] mTLS for service-to-service (optional)
- [ ] Egress firewall rules

### Audit & Compliance
- [ ] Enable Kubernetes audit logging
- [ ] Configure log retention (90 days recommended)
- [ ] Set up SIEM integration
- [ ] Document data flow for compliance

---

## Rollback Procedures

### Quick Rollback
```bash
# Rollback deployment to previous revision
kubectl rollout undo deployment/litellm -n litellm
kubectl rollout undo deployment/agentgateway -n agentgateway
```

### Full Rollback
```bash
# Revert to previous Git commit
git revert HEAD
git push

# Re-apply manifests
kubectl apply -k kubernetes/overlays/production/
```

---

## Contacts

| Role | Name | Contact |
|------|------|---------|
| Platform Team Lead | TBD | TBD |
| On-Call Engineer | TBD | TBD |
| Security Contact | TBD | TBD |
| Database Admin | TBD | TBD |

---

## Sign-Off

| Reviewer | Date | Status |
|----------|------|--------|
| Platform Engineering | | [ ] Approved |
| Security Team | | [ ] Approved |
| SRE Team | | [ ] Approved |
| Compliance | | [ ] Approved |
