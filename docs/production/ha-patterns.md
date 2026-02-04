# High Availability Patterns

## Document Information
| Field | Value |
|-------|-------|
| Version | 1.0 |
| Last Updated | 2026-02 |
| Owner | Platform Team |

## Overview

This document describes high availability (HA) patterns for the AI Gateway Platform, covering single-region HA, multi-region deployment, and disaster recovery strategies.

---

## 1. Availability Targets

| Tier | Availability | Monthly Downtime | RPO | RTO |
|------|-------------|------------------|-----|-----|
| Standard | 99.9% | ~43 min | 1 hour | 4 hours |
| High | 99.95% | ~22 min | 15 min | 1 hour |
| Critical | 99.99% | ~4 min | 5 min | 15 min |

---

## 2. Single-Region HA Architecture

```
                         ┌─────────────────────────────────────────┐
                         │            Load Balancer (NLB)          │
                         │         (Multi-AZ, Health Checks)       │
                         └─────────────────────────────────────────┘
                                            │
              ┌─────────────────────────────┼─────────────────────────────┐
              │                             │                             │
    ┌─────────▼─────────┐       ┌──────────▼──────────┐       ┌─────────▼─────────┐
    │      AZ-1         │       │        AZ-2          │       │      AZ-3         │
    │  ┌─────────────┐  │       │  ┌─────────────┐    │       │  ┌─────────────┐  │
    │  │  LiteLLM    │  │       │  │  LiteLLM    │    │       │  │  LiteLLM    │  │
    │  │  (replica)  │  │       │  │  (replica)  │    │       │  │  (replica)  │  │
    │  └─────────────┘  │       │  └─────────────┘    │       │  └─────────────┘  │
    │  ┌─────────────┐  │       │  ┌─────────────┐    │       │  ┌─────────────┐  │
    │  │Agent Gateway│  │       │  │Agent Gateway│    │       │  │Agent Gateway│  │
    │  │  (replica)  │  │       │  │  (replica)  │    │       │  │  (replica)  │  │
    │  └─────────────┘  │       │  └─────────────┘    │       │  └─────────────┘  │
    │  ┌─────────────┐  │       │  ┌─────────────┐    │       │  ┌─────────────┐  │
    │  │   vLLM      │  │       │  │    vLLM     │    │       │  │   vLLM      │  │
    │  │  (engine)   │  │       │  │   (engine)  │    │       │  │  (engine)   │  │
    │  └─────────────┘  │       │  └─────────────┘    │       │  └─────────────┘  │
    │  ┌─────────────┐  │       │  ┌─────────────┐    │       │  ┌─────────────┐  │
    │  │PostgreSQL   │  │◄──────┤  │PostgreSQL   │    │◄──────┤  │PostgreSQL   │  │
    │  │ (primary)   │  │ sync  │  │ (replica)   │    │ sync  │  │ (replica)   │  │
    │  └─────────────┘  │       │  └─────────────┘    │       │  └─────────────┘  │
    │  ┌─────────────┐  │       │  ┌─────────────┐    │       │  ┌─────────────┐  │
    │  │Redis        │  │◄──────┤  │Redis        │    │◄──────┤  │Redis        │  │
    │  │ (primary)   │  │       │  │ (replica)   │    │       │  │ (replica)   │  │
    │  └─────────────┘  │       │  └─────────────┘    │       │  └─────────────┘  │
    └───────────────────┘       └─────────────────────┘       └───────────────────┘
```

### 2.1 Component Distribution

```yaml
# Pod anti-affinity to spread across AZs
apiVersion: apps/v1
kind: Deployment
metadata:
  name: litellm
spec:
  replicas: 3
  template:
    spec:
      affinity:
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            - labelSelector:
                matchLabels:
                  app: litellm
              topologyKey: topology.kubernetes.io/zone
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: topology.kubernetes.io/zone
          whenUnsatisfiable: DoNotSchedule
          labelSelector:
            matchLabels:
              app: litellm
```

### 2.2 Pod Disruption Budgets

```yaml
# Ensure minimum availability during updates/node maintenance
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: litellm-pdb
spec:
  minAvailable: 2  # At least 2 pods always running
  selector:
    matchLabels:
      app: litellm
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: postgres-pdb
spec:
  maxUnavailable: 1  # Allow 1 pod to be disrupted
  selector:
    matchLabels:
      app: postgresql
```

### 2.3 Health Checks

```yaml
# Comprehensive health checks for LiteLLM
apiVersion: apps/v1
kind: Deployment
metadata:
  name: litellm
spec:
  template:
    spec:
      containers:
        - name: litellm
          livenessProbe:
            httpGet:
              path: /health/liveliness
              port: 4000
            initialDelaySeconds: 30
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /health/readiness
              port: 4000
            initialDelaySeconds: 10
            periodSeconds: 5
            timeoutSeconds: 3
            failureThreshold: 2
          startupProbe:
            httpGet:
              path: /health
              port: 4000
            initialDelaySeconds: 10
            periodSeconds: 5
            failureThreshold: 30  # 2.5 min max startup
```

---

## 3. Multi-Region Architecture

```
                              ┌─────────────────────────────┐
                              │      Global DNS (Route53)   │
                              │    Latency-based routing    │
                              └─────────────────────────────┘
                                            │
              ┌─────────────────────────────┼─────────────────────────────┐
              │                             │                             │
    ┌─────────▼─────────┐       ┌──────────▼──────────┐       ┌─────────▼─────────┐
    │   us-east-1       │       │    us-west-2        │       │    eu-west-1      │
    │   (PRIMARY)       │       │   (SECONDARY)       │       │   (SECONDARY)     │
    │                   │       │                     │       │                   │
    │  ┌─────────────┐  │       │  ┌─────────────┐   │       │  ┌─────────────┐  │
    │  │ AI Gateway  │  │       │  │ AI Gateway  │   │       │  │ AI Gateway  │  │
    │  │   Stack     │  │       │  │   Stack     │   │       │  │   Stack     │  │
    │  └─────────────┘  │       │  └─────────────┘   │       │  └─────────────┘  │
    │                   │       │                     │       │                   │
    │  ┌─────────────┐  │       │  ┌─────────────┐   │       │  ┌─────────────┐  │
    │  │ PostgreSQL  │──────────┤  │ PostgreSQL  │   │       │  │ PostgreSQL  │  │
    │  │  (writer)   │  │async  │  │ (read-only) │   │       │  │ (read-only) │  │
    │  └─────────────┘  │       │  └─────────────┘   │       │  └─────────────┘  │
    │                   │              ▲                       │       ▲          │
    │                   │              │                       │       │          │
    │                   │              └───────────────────────│───────┘          │
    │                   │                 Cross-region         │                  │
    │                   │                 replication          │                  │
    └───────────────────┘                                      └──────────────────┘
                              ┌─────────────────────────────┐
                              │    Vault Enterprise         │
                              │   (Performance Replication) │
                              └─────────────────────────────┘
```

### 3.1 DNS Configuration (Route53)

```hcl
# Terraform - Global DNS with failover
resource "aws_route53_health_check" "primary" {
  fqdn              = "gateway.us-east-1.example.com"
  port              = 443
  type              = "HTTPS"
  resource_path     = "/health"
  failure_threshold = 3
  request_interval  = 10

  tags = {
    Name = "ai-gateway-primary-health"
  }
}

resource "aws_route53_record" "gateway" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "gateway.example.com"
  type    = "A"

  latency_routing_policy {
    region = "us-east-1"
  }

  set_identifier = "primary"

  alias {
    name                   = aws_lb.us_east_1.dns_name
    zone_id                = aws_lb.us_east_1.zone_id
    evaluate_target_health = true
  }

  health_check_id = aws_route53_health_check.primary.id
}

resource "aws_route53_record" "gateway_secondary" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "gateway.example.com"
  type    = "A"

  latency_routing_policy {
    region = "us-west-2"
  }

  set_identifier = "secondary"

  alias {
    name                   = aws_lb.us_west_2.dns_name
    zone_id                = aws_lb.us_west_2.zone_id
    evaluate_target_health = true
  }
}
```

### 3.2 Cross-Region Database Replication

```yaml
# PostgreSQL cross-region replication using CloudNativePG
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: postgres-primary
  namespace: ai-gateway
spec:
  instances: 3

  postgresql:
    parameters:
      max_connections: "200"
      shared_buffers: "2GB"
      wal_level: "logical"
      max_wal_senders: "10"
      max_replication_slots: "10"

  bootstrap:
    initdb:
      database: litellm
      owner: litellm

  storage:
    size: 500Gi
    storageClass: gp3

  replica:
    enabled: true
    source: postgres-primary

  externalClusters:
    - name: postgres-secondary-us-west-2
      connectionParameters:
        host: postgres.us-west-2.internal
        user: replication
        dbname: litellm
      barmanObjectStore:
        destinationPath: s3://postgres-backup-us-west-2/
        s3Credentials:
          accessKeyId:
            name: aws-creds
            key: ACCESS_KEY_ID
          secretAccessKey:
            name: aws-creds
            key: SECRET_ACCESS_KEY
```

---

## 4. Failover Procedures

### 4.1 Automatic Failover (Component Level)

| Component | Failover Mechanism | Detection Time | Recovery Time |
|-----------|-------------------|----------------|---------------|
| LiteLLM | Kubernetes + LoadBalancer | 10-30s | < 1 min |
| Agent Gateway | Kubernetes + LoadBalancer | 10-30s | < 1 min |
| vLLM | KEDA + Router health checks | 30-60s | 1-5 min |
| PostgreSQL | Patroni/CloudNativePG | 30s | < 1 min |
| Redis | Sentinel/Cluster | 5-30s | < 1 min |
| Vault | Raft consensus | 10-30s | < 1 min |

### 4.2 Manual Regional Failover

```bash
#!/bin/bash
# failover-to-secondary.sh
# Execute regional failover when primary region is degraded

set -euo pipefail

PRIMARY_REGION="us-east-1"
SECONDARY_REGION="us-west-2"

echo "=== Regional Failover: $PRIMARY_REGION -> $SECONDARY_REGION ==="

# Step 1: Verify secondary region health
echo "Checking secondary region health..."
HEALTH=$(curl -sf https://gateway.$SECONDARY_REGION.internal/health || echo "FAILED")
if [[ "$HEALTH" != *"healthy"* ]]; then
    echo "ERROR: Secondary region unhealthy. Aborting."
    exit 1
fi

# Step 2: Promote secondary database
echo "Promoting secondary PostgreSQL..."
kubectl --context $SECONDARY_REGION exec -n ai-gateway postgres-0 -- \
    patronictl switchover --master postgres-0 --candidate postgres-1 --force

# Step 3: Update DNS weights
echo "Updating DNS routing..."
aws route53 change-resource-record-sets \
    --hosted-zone-id $ZONE_ID \
    --change-batch '{
        "Changes": [{
            "Action": "UPSERT",
            "ResourceRecordSet": {
                "Name": "gateway.example.com",
                "Type": "A",
                "SetIdentifier": "primary",
                "Weight": 0,
                "AliasTarget": {
                    "HostedZoneId": "'$PRIMARY_ALB_ZONE'",
                    "DNSName": "'$PRIMARY_ALB_DNS'",
                    "EvaluateTargetHealth": true
                }
            }
        }]
    }'

# Step 4: Scale up secondary
echo "Scaling up secondary region..."
kubectl --context $SECONDARY_REGION scale deployment litellm --replicas=5 -n ai-gateway
kubectl --context $SECONDARY_REGION scale deployment agentgateway --replicas=3 -n ai-gateway

# Step 5: Verify
echo "Verifying failover..."
sleep 30
curl -sf https://gateway.example.com/health

echo "=== Failover Complete ==="
echo "Primary traffic now routed to $SECONDARY_REGION"
echo ""
echo "POST-FAILOVER ACTIONS:"
echo "1. Investigate primary region issue"
echo "2. Monitor error rates and latency"
echo "3. Plan failback when primary recovers"
```

### 4.3 Failback Procedure

```bash
#!/bin/bash
# failback-to-primary.sh

set -euo pipefail

PRIMARY_REGION="us-east-1"
SECONDARY_REGION="us-west-2"

echo "=== Regional Failback: $SECONDARY_REGION -> $PRIMARY_REGION ==="

# Step 1: Verify primary region recovered
echo "Verifying primary region health..."
HEALTH=$(curl -sf https://gateway.$PRIMARY_REGION.internal/health || echo "FAILED")
if [[ "$HEALTH" != *"healthy"* ]]; then
    echo "ERROR: Primary region not ready. Aborting."
    exit 1
fi

# Step 2: Sync data back to primary (if needed)
echo "Checking data sync status..."
kubectl --context $PRIMARY_REGION exec -n ai-gateway postgres-0 -- \
    psql -c "SELECT pg_last_wal_replay_lsn();"

# Step 3: Gradual traffic shift (canary)
echo "Starting canary traffic shift (10%)..."
aws route53 change-resource-record-sets \
    --hosted-zone-id $ZONE_ID \
    --change-batch '{
        "Changes": [{
            "Action": "UPSERT",
            "ResourceRecordSet": {
                "Name": "gateway.example.com",
                "Type": "A",
                "SetIdentifier": "primary",
                "Weight": 10,
                "AliasTarget": {
                    "HostedZoneId": "'$PRIMARY_ALB_ZONE'",
                    "DNSName": "'$PRIMARY_ALB_DNS'",
                    "EvaluateTargetHealth": true
                }
            }
        }]
    }'

echo "Monitoring for 5 minutes..."
sleep 300

# Check error rates
ERROR_RATE=$(curl -s "http://prometheus:9090/api/v1/query?query=rate(http_requests_total{status=~\"5..\"}[5m])" | jq '.data.result[0].value[1]')
if (( $(echo "$ERROR_RATE > 0.01" | bc -l) )); then
    echo "ERROR: High error rate detected. Aborting failback."
    exit 1
fi

# Step 4: Increase traffic gradually
for WEIGHT in 25 50 75 100; do
    echo "Shifting to $WEIGHT% traffic..."
    # Update DNS weight
    sleep 300  # 5 min between shifts
done

echo "=== Failback Complete ==="
```

---

## 5. Disaster Recovery

### 5.1 Backup Strategy

| Data Type | Backup Frequency | Retention | Storage |
|-----------|-----------------|-----------|---------|
| PostgreSQL (full) | Daily | 30 days | S3 Cross-Region |
| PostgreSQL (WAL) | Continuous | 7 days | S3 Cross-Region |
| Vault (snapshots) | Hourly | 7 days | S3 Cross-Region |
| Redis (RDB) | Hourly | 24 hours | S3 Same-Region |
| Configuration | On change | Unlimited | Git |
| Secrets metadata | Daily | 30 days | Vault backup |

### 5.2 Recovery Procedures

```bash
#!/bin/bash
# disaster-recovery.sh
# Full DR restore from backup

set -euo pipefail

DR_REGION="eu-west-1"
BACKUP_BUCKET="s3://ai-gateway-backups-dr"
RESTORE_TIMESTAMP=${1:-"latest"}

echo "=== Disaster Recovery to $DR_REGION ==="

# Step 1: Bootstrap Kubernetes cluster
echo "Ensuring EKS cluster is ready..."
aws eks update-kubeconfig --region $DR_REGION --name ai-gateway-dr

# Step 2: Deploy base infrastructure
echo "Deploying infrastructure..."
kubectl apply -k kubernetes/overlays/dr/

# Step 3: Restore Vault
echo "Restoring Vault..."
VAULT_SNAPSHOT=$(aws s3 ls $BACKUP_BUCKET/vault/ | tail -1 | awk '{print $4}')
aws s3 cp $BACKUP_BUCKET/vault/$VAULT_SNAPSHOT /tmp/vault-snapshot.snap
kubectl exec -n ai-gateway vault-0 -- vault operator raft snapshot restore /tmp/vault-snapshot.snap

# Step 4: Restore PostgreSQL
echo "Restoring PostgreSQL..."
kubectl apply -f - <<EOF
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: postgres-dr
spec:
  instances: 3
  bootstrap:
    recovery:
      source: postgres-backup
  externalClusters:
    - name: postgres-backup
      barmanObjectStore:
        destinationPath: $BACKUP_BUCKET/postgres/
        s3Credentials:
          accessKeyId:
            name: aws-creds
            key: ACCESS_KEY_ID
          secretAccessKey:
            name: aws-creds
            key: SECRET_ACCESS_KEY
        wal:
          maxParallel: 8
EOF

# Step 5: Wait for services
echo "Waiting for services to be ready..."
kubectl wait --for=condition=ready pod -l app=litellm -n ai-gateway --timeout=600s
kubectl wait --for=condition=ready pod -l app=postgres -n ai-gateway --timeout=600s

# Step 6: Verify
echo "Running verification tests..."
./scripts/test-all.sh

echo "=== DR Recovery Complete ==="
echo "Update DNS to point to DR region when ready"
```

### 5.3 RTO/RPO Verification

```bash
#!/bin/bash
# dr-drill.sh
# Run quarterly DR drill

echo "=== DR Drill Started: $(date) ==="

START_TIME=$(date +%s)

# Simulate primary failure
echo "Simulating primary region failure..."

# Execute failover
./failover-to-secondary.sh

FAILOVER_TIME=$(date +%s)
RTO=$((FAILOVER_TIME - START_TIME))

# Verify data
echo "Verifying data integrity..."
LAST_TX_PRIMARY=$(kubectl --context us-east-1 exec postgres-0 -- psql -t -c "SELECT max(created_at) FROM cost_tracking_daily;")
LAST_TX_SECONDARY=$(kubectl --context us-west-2 exec postgres-0 -- psql -t -c "SELECT max(created_at) FROM cost_tracking_daily;")

RPO_SECONDS=$(($(date -d "$LAST_TX_PRIMARY" +%s) - $(date -d "$LAST_TX_SECONDARY" +%s)))

echo ""
echo "=== DR Drill Results ==="
echo "RTO: ${RTO}s (target: 900s)"
echo "RPO: ${RPO_SECONDS}s (target: 300s)"
echo ""

if [ $RTO -le 900 ] && [ $RPO_SECONDS -le 300 ]; then
    echo "✓ DR drill PASSED"
else
    echo "✗ DR drill FAILED - review and remediate"
fi

# Failback
read -p "Execute failback? (yes/no) " CONFIRM
if [ "$CONFIRM" = "yes" ]; then
    ./failback-to-primary.sh
fi
```

---

## 6. Monitoring for HA

### 6.1 Key Availability Metrics

```yaml
# Prometheus alerting rules for HA
groups:
  - name: high-availability
    rules:
      - alert: InsufficientReplicas
        expr: |
          kube_deployment_status_replicas_available{deployment=~"litellm|agentgateway"}
          < kube_deployment_spec_replicas{deployment=~"litellm|agentgateway"} * 0.5
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "{{ $labels.deployment }} has < 50% replicas available"

      - alert: SingleAZDeployment
        expr: |
          count by (deployment) (
            kube_pod_info{pod=~"litellm.*|agentgateway.*"}
            * on(node) group_left(zone)
            kube_node_labels
          ) < 2
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "{{ $labels.deployment }} running in single AZ"

      - alert: DatabaseReplicationLag
        expr: pg_replication_lag_seconds > 30
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "PostgreSQL replication lag > 30s"

      - alert: RegionHealthDegraded
        expr: |
          sum by (region) (up{job="ai-gateway"})
          / count by (region) (up{job="ai-gateway"}) < 0.8
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Region {{ $labels.region }} health < 80%"
```

---

## Appendix: HA Checklist

### Pre-Production Checklist

- [ ] Multi-AZ deployment verified
- [ ] Pod anti-affinity configured
- [ ] PodDisruptionBudgets in place
- [ ] Health checks tuned and tested
- [ ] Database replication verified
- [ ] Redis HA configured
- [ ] Vault HA configured
- [ ] Load balancer health checks
- [ ] DNS failover tested
- [ ] Backup/restore tested
- [ ] Runbooks documented
- [ ] On-call rotation established
- [ ] DR drill scheduled
