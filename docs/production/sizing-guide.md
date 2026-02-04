# Production Sizing Guide

## Document Information
| Field | Value |
|-------|-------|
| Version | 1.0 |
| Last Updated | 2026-02 |
| Owner | Platform Team |

## Overview

This guide provides sizing recommendations for the AI Gateway Platform based on expected workload characteristics. Sizes are categorized into Small, Medium, Large, and Enterprise tiers.

---

## 1. Workload Profiles

### 1.1 Profile Definitions

| Profile | Requests/sec | Concurrent Users | Daily Tokens | Use Case |
|---------|--------------|------------------|--------------|----------|
| **Small** | 1-10 | 50-100 | < 10M | Dev/staging, small teams |
| **Medium** | 10-100 | 100-500 | 10M-100M | Mid-size org, multiple teams |
| **Large** | 100-500 | 500-2000 | 100M-1B | Enterprise, high throughput |
| **Enterprise** | 500+ | 2000+ | 1B+ | Multi-region, mission-critical |

### 1.2 Request Characteristics

| Metric | Typical Range | Planning Factor |
|--------|---------------|-----------------|
| Avg input tokens | 500-2000 | Use 1500 |
| Avg output tokens | 200-1000 | Use 500 |
| Streaming ratio | 60-80% | Use 70% |
| Cache hit rate | 10-30% | Use 15% |
| Peak/avg ratio | 2-5x | Use 3x |

---

## 2. Component Sizing

### 2.1 LiteLLM Proxy

LiteLLM is CPU and memory bound. Scale horizontally for throughput.

| Size | Replicas | CPU (request/limit) | Memory (request/limit) | Max RPS |
|------|----------|---------------------|------------------------|---------|
| Small | 2 | 500m / 1000m | 512Mi / 1Gi | 50 |
| Medium | 3 | 1000m / 2000m | 1Gi / 2Gi | 200 |
| Large | 5 | 2000m / 4000m | 2Gi / 4Gi | 500 |
| Enterprise | 10+ | 2000m / 4000m | 4Gi / 8Gi | 1000+ |

**HPA Configuration:**
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: litellm
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: litellm
  minReplicas: 2   # Small: 2, Medium: 3, Large: 5
  maxReplicas: 20  # 4x min for burst
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 25
          periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
        - type: Percent
          value: 100
          periodSeconds: 15
```

### 2.2 Agent Gateway

Agent Gateway (Rust) is highly efficient. Fewer replicas needed.

| Size | Replicas | CPU (request/limit) | Memory (request/limit) | Max RPS |
|------|----------|---------------------|------------------------|---------|
| Small | 2 | 250m / 500m | 256Mi / 512Mi | 500 |
| Medium | 2 | 500m / 1000m | 512Mi / 1Gi | 2000 |
| Large | 3 | 1000m / 2000m | 1Gi / 2Gi | 5000 |
| Enterprise | 5+ | 2000m / 4000m | 2Gi / 4Gi | 10000+ |

### 2.3 vLLM (Self-Hosted Inference)

GPU-bound. Size based on model and throughput needs.

| Model | GPU Type | GPU Count | Memory | Throughput (tok/s) |
|-------|----------|-----------|--------|-------------------|
| Llama-3.1-8B | A10G | 1 | 24GB | 2000-3000 |
| Llama-3.1-8B | A100-40GB | 1 | 40GB | 4000-5000 |
| Llama-3.1-70B | A100-40GB | 2 (TP) | 80GB | 500-800 |
| Llama-3.1-70B | A100-80GB | 2 (TP) | 160GB | 1000-1500 |
| Llama-3.1-70B | H100 | 2 (TP) | 160GB | 2000-3000 |

**Production Stack Configuration:**
```yaml
# vLLM Production Stack Helm values
replicaCount:
  router: 2
  engine:
    min: 1
    max: 4

engine:
  resources:
    requests:
      nvidia.com/gpu: 1
      memory: "32Gi"
      cpu: "8"
    limits:
      nvidia.com/gpu: 1
      memory: "48Gi"
      cpu: "16"

  modelSpec:
    - name: "llama-3.1-8b"
      repository: "meta-llama/Llama-3.1-8B-Instruct"
      tensorParallelSize: 1
      maxModelLen: 32768

  autoscaling:
    enabled: true
    minReplicas: 1
    maxReplicas: 4
    metrics:
      - type: prometheus
        prometheus:
          query: vllm:num_requests_running
          threshold: 10
```

### 2.4 PostgreSQL

| Size | Type | vCPU | Memory | Storage | IOPS |
|------|------|------|--------|---------|------|
| Small | Single | 2 | 4GB | 50GB SSD | 3000 |
| Medium | Primary + Replica | 4 | 8GB | 100GB SSD | 6000 |
| Large | Primary + 2 Replicas | 8 | 16GB | 500GB SSD | 12000 |
| Enterprise | HA Cluster (3 nodes) | 16 | 32GB | 1TB NVMe | 20000+ |

**Connection Pool Settings:**
```yaml
# PgBouncer configuration
pool_mode: transaction
default_pool_size: 20        # Small
# default_pool_size: 50      # Medium
# default_pool_size: 100     # Large
max_client_conn: 1000
reserve_pool_size: 5
```

### 2.5 Redis

| Size | Type | Memory | Persistence |
|------|------|--------|-------------|
| Small | Single | 1GB | RDB every 5m |
| Medium | Primary + Replica | 4GB | RDB + AOF |
| Large | Cluster (3 primary) | 8GB per node | RDB + AOF |
| Enterprise | Cluster (6 nodes) | 16GB per node | AOF always |

### 2.6 Vault

| Size | Type | CPU | Memory | Storage |
|------|------|-----|--------|---------|
| Small | Single (dev) | 500m | 512Mi | 1GB |
| Medium | HA (3 nodes) | 1000m | 1Gi | 10GB |
| Large | HA (5 nodes) | 2000m | 2Gi | 50GB |
| Enterprise | HA + DR | 4000m | 4Gi | 100GB |

### 2.7 Observability Stack

| Component | Small | Medium | Large | Enterprise |
|-----------|-------|--------|-------|------------|
| OTel Collector | 1 x 500m/512Mi | 2 x 1000m/1Gi | 3 x 2000m/2Gi | 5 x 4000m/4Gi |
| Prometheus | 1 x 1Gi/4Gi | 1 x 2Gi/8Gi | 2 x 4Gi/16Gi | HA + Thanos |
| Grafana | 1 x 250m/512Mi | 2 x 500m/1Gi | 2 x 1000m/2Gi | 3 x 2000m/4Gi |
| Jaeger | Single | All-in-one | Distributed | Elastic backend |

---

## 3. Infrastructure Requirements

### 3.1 Kubernetes Cluster Sizing

| Size | Control Plane | Worker Nodes (CPU) | Worker Nodes (GPU) |
|------|---------------|--------------------|--------------------|
| Small | Managed (3 node) | 3 x m5.xlarge | 1 x g4dn.xlarge |
| Medium | Managed (3 node) | 5 x m5.2xlarge | 2 x g4dn.2xlarge |
| Large | Managed (5 node) | 10 x m5.4xlarge | 4 x g5.4xlarge |
| Enterprise | Dedicated (5 node) | 20 x m5.8xlarge | 8 x p4d.24xlarge |

### 3.2 Network Requirements

| Size | Ingress Bandwidth | Internal Bandwidth | VPC Endpoints |
|------|-------------------|-------------------|---------------|
| Small | 100 Mbps | 1 Gbps | Optional |
| Medium | 500 Mbps | 10 Gbps | Recommended |
| Large | 1 Gbps | 25 Gbps | Required |
| Enterprise | 10 Gbps | 100 Gbps | Required |

### 3.3 Storage Requirements

| Component | Small | Medium | Large | Enterprise |
|-----------|-------|--------|-------|------------|
| PostgreSQL | 50 GB | 200 GB | 1 TB | 5 TB |
| Redis | 5 GB | 20 GB | 50 GB | 200 GB |
| Prometheus | 50 GB | 200 GB | 1 TB | 5 TB |
| Model Cache | 100 GB | 500 GB | 2 TB | 10 TB |

---

## 4. Cost Estimation (AWS, us-east-1)

### 4.1 Monthly Infrastructure Cost

| Component | Small | Medium | Large | Enterprise |
|-----------|-------|--------|-------|------------|
| EKS Control Plane | $73 | $73 | $146 | $146 |
| EC2 Workers (CPU) | $300 | $800 | $3,200 | $12,800 |
| EC2 Workers (GPU) | $380 | $1,520 | $6,000 | $48,000 |
| RDS PostgreSQL | $50 | $200 | $800 | $3,200 |
| ElastiCache Redis | $50 | $200 | $600 | $2,400 |
| EBS Storage | $50 | $200 | $800 | $4,000 |
| Data Transfer | $50 | $200 | $1,000 | $5,000 |
| **Total** | **~$950** | **~$3,200** | **~$12,500** | **~$75,000** |

### 4.2 LLM API Cost (assuming 30% external)

| Size | Daily Tokens | External (30%) | Monthly Cost |
|------|--------------|----------------|--------------|
| Small | 10M | 3M | ~$150 |
| Medium | 100M | 30M | ~$1,500 |
| Large | 1B | 300M | ~$15,000 |
| Enterprise | 10B | 3B | ~$150,000 |

---

## 5. Capacity Planning

### 5.1 Growth Model

```
Required_Capacity = Current_Load × Growth_Factor × Peak_Factor × Safety_Margin

Where:
- Growth_Factor = (1 + monthly_growth_rate)^months_ahead
- Peak_Factor = typically 2-3x average
- Safety_Margin = 1.2-1.5x
```

### 5.2 Scaling Triggers

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| CPU utilization | >70% | >85% | Scale horizontally |
| Memory utilization | >75% | >90% | Scale vertically first |
| Request latency (P95) | >2s | >5s | Investigate bottleneck |
| Error rate | >1% | >5% | Incident response |
| Queue depth | >100 | >500 | Add capacity |
| GPU utilization | >80% | >95% | Add GPU nodes |

### 5.3 Quarterly Review Checklist

- [ ] Review actual vs projected usage
- [ ] Analyze cost per request trends
- [ ] Evaluate cache effectiveness
- [ ] Check for hotspots/bottlenecks
- [ ] Update capacity projections
- [ ] Plan infrastructure changes

---

## Appendix A: Instance Type Reference

### AWS Instance Types

| Use Case | Instance Type | vCPU | Memory | Network | Notes |
|----------|---------------|------|--------|---------|-------|
| Gateway | m5.xlarge | 4 | 16GB | Up to 10 Gbps | Balanced |
| Gateway | c5.2xlarge | 8 | 16GB | Up to 10 Gbps | CPU optimized |
| Database | r5.2xlarge | 8 | 64GB | Up to 10 Gbps | Memory optimized |
| GPU (Small) | g4dn.xlarge | 4 | 16GB + T4 | Up to 25 Gbps | Cost effective |
| GPU (Medium) | g5.4xlarge | 16 | 64GB + A10G | Up to 25 Gbps | Good balance |
| GPU (Large) | p4d.24xlarge | 96 | 1152GB + 8xA100 | 400 Gbps | High performance |

### GCP Instance Types

| Use Case | Instance Type | vCPU | Memory | GPU | Notes |
|----------|---------------|------|--------|-----|-------|
| Gateway | n2-standard-4 | 4 | 16GB | - | Standard |
| Gateway | c2-standard-8 | 8 | 32GB | - | Compute optimized |
| Database | n2-highmem-8 | 8 | 64GB | - | Memory optimized |
| GPU | a2-highgpu-1g | 12 | 85GB | 1xA100 | Single GPU |
| GPU | a2-highgpu-4g | 48 | 340GB | 4xA100 | Multi-GPU |
