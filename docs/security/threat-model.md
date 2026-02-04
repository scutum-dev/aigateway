# AI Gateway Platform - Threat Model

## Document Information
| Field | Value |
|-------|-------|
| Version | 1.0 |
| Last Updated | 2026-02 |
| Classification | Internal |
| Review Cycle | Quarterly |

## 1. System Overview

### 1.1 Architecture Context
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              TRUST BOUNDARY: CLUSTER                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                        TRUST BOUNDARY: GATEWAY                          ││
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐              ││
│  │  │   LiteLLM    │───▶│Agent Gateway │───▶│    vLLM      │              ││
│  │  │   (L7 Proxy) │    │ (Data Plane) │    │  (Inference) │              ││
│  │  └──────────────┘    └──────────────┘    └──────────────┘              ││
│  │         │                   │                   │                       ││
│  │         ▼                   ▼                   ▼                       ││
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐              ││
│  │  │  PostgreSQL  │    │    Vault     │    │    Redis     │              ││
│  │  │   (State)    │    │  (Secrets)   │    │   (Cache)    │              ││
│  │  └──────────────┘    └──────────────┘    └──────────────┘              ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
         ▲                                                    │
         │                                                    ▼
    ┌─────────┐                                    ┌──────────────────┐
    │ Clients │                                    │ External LLM APIs│
    │(Agents) │                                    │ (OpenAI/Anthropic)│
    └─────────┘                                    └──────────────────┘
```

### 1.2 Data Flow Summary
1. **Inbound**: Client → Ingress → LiteLLM → Agent Gateway → Backend (vLLM/External)
2. **Secrets**: Vault → Agent Gateway → External API calls
3. **Telemetry**: All components → OTel Collector → Prometheus/Jaeger
4. **State**: LiteLLM ↔ PostgreSQL (spend tracking, keys)

## 2. Assets

### 2.1 Critical Assets
| Asset | Classification | Location | Owner |
|-------|---------------|----------|-------|
| API Provider Keys | SECRET | Vault | Platform Team |
| User API Keys | SECRET | PostgreSQL | Platform Team |
| LLM Request/Response Data | CONFIDENTIAL | In-transit, Redis cache | Data Owner |
| Cost/Spend Data | INTERNAL | PostgreSQL | FinOps Team |
| Cedar Policies | INTERNAL | ConfigMap/Vault | Security Team |
| TLS Certificates | SECRET | Cert-Manager/Vault | Platform Team |

### 2.2 Data Classification
- **SECRET**: Credentials, tokens, private keys - encrypted at rest, audit logged
- **CONFIDENTIAL**: PII, business-sensitive prompts/responses - encrypted, access-controlled
- **INTERNAL**: Operational data, metrics - access-controlled
- **PUBLIC**: Health endpoints, public documentation

## 3. Threat Actors

| Actor | Motivation | Capability | Likelihood |
|-------|------------|------------|------------|
| External Attacker | Data theft, service disruption | Medium-High | Medium |
| Malicious Insider | Data exfiltration, sabotage | High | Low |
| Compromised Agent | Lateral movement, data access | Medium | Medium |
| Supply Chain | Backdoor, credential theft | High | Low |

## 4. Threats (STRIDE Analysis)

### 4.1 Spoofing

| ID | Threat | Component | Mitigation | Priority |
|----|--------|-----------|------------|----------|
| S1 | API key impersonation | LiteLLM | Key rotation, IP allowlisting, anomaly detection | HIGH |
| S2 | Service identity spoofing | Agent Gateway | mTLS between services, SPIFFE/SPIRE | HIGH |
| S3 | JWT token forgery | Agent Gateway | RS256 signing, short expiry, token binding | MEDIUM |
| S4 | MCP server impersonation | MCP Gateway | Server authentication, allowlisting | MEDIUM |

### 4.2 Tampering

| ID | Threat | Component | Mitigation | Priority |
|----|--------|-----------|------------|----------|
| T1 | Prompt injection via API | LiteLLM/Agent GW | Input validation, content filtering | HIGH |
| T2 | Response manipulation | Agent Gateway | Response signing, integrity checks | MEDIUM |
| T3 | Configuration tampering | Kubernetes | GitOps, admission controllers, RBAC | HIGH |
| T4 | Database record modification | PostgreSQL | Audit logging, row-level security | MEDIUM |

### 4.3 Repudiation

| ID | Threat | Component | Mitigation | Priority |
|----|--------|-----------|------------|----------|
| R1 | Denied API usage | LiteLLM | Immutable audit logs, request signing | HIGH |
| R2 | Cost attribution disputes | FinOps Reporter | Tamper-evident spend logs | MEDIUM |
| R3 | Policy change denial | Vault/Cedar | Git-backed policies, change audit | MEDIUM |

### 4.4 Information Disclosure

| ID | Threat | Component | Mitigation | Priority |
|----|--------|-----------|------------|----------|
| I1 | API key exposure in logs | All | Log scrubbing, secret detection | CRITICAL |
| I2 | Prompt/response leakage | Redis cache | Encryption at rest, short TTL | HIGH |
| I3 | Model output exfiltration | Agent Gateway | DLP policies, output filtering | HIGH |
| I4 | Side-channel via timing | vLLM | Request padding, rate limiting | LOW |

### 4.5 Denial of Service

| ID | Threat | Component | Mitigation | Priority |
|----|--------|-----------|------------|----------|
| D1 | Token exhaustion attack | LiteLLM | Budget limits, rate limiting | HIGH |
| D2 | Connection pool exhaustion | Agent Gateway | Connection limits, circuit breakers | HIGH |
| D3 | GPU memory exhaustion | vLLM | Request queuing, memory limits | MEDIUM |
| D4 | Cache poisoning | Redis | Authentication, input validation | MEDIUM |

### 4.6 Elevation of Privilege

| ID | Threat | Component | Mitigation | Priority |
|----|--------|-----------|------------|----------|
| E1 | Cross-tenant data access | LiteLLM | Team isolation, Cedar policies | CRITICAL |
| E2 | Vault token escalation | Vault | Least-privilege policies, token TTL | HIGH |
| E3 | Container escape | All Pods | Seccomp, AppArmor, non-root | HIGH |
| E4 | RBAC bypass | Kubernetes | Audit logging, admission webhooks | HIGH |

## 5. Attack Trees

### 5.1 Credential Theft Attack Tree
```
Goal: Steal API Provider Keys
├── 1. Extract from Vault [CRITICAL]
│   ├── 1.1 Compromise Vault token
│   │   ├── 1.1.1 Steal from pod environment
│   │   ├── 1.1.2 Intercept token renewal
│   │   └── 1.1.3 Exploit Vault vulnerability
│   └── 1.2 Access Vault storage backend
│       └── 1.2.1 Compromise etcd/consul
├── 2. Extract from Memory [HIGH]
│   ├── 2.1 Container escape + memory dump
│   └── 2.2 Core dump analysis
├── 3. Extract from Logs [MEDIUM]
│   ├── 3.1 Access application logs
│   └── 3.2 Access OTel traces
└── 4. Man-in-the-Middle [MEDIUM]
    ├── 4.1 Compromise service mesh
    └── 4.2 DNS hijacking
```

### 5.2 Budget Bypass Attack Tree
```
Goal: Exceed Budget Without Detection
├── 1. Direct API Access [HIGH]
│   ├── 1.1 Bypass LiteLLM proxy
│   │   └── 1.1.1 Direct vLLM access
│   └── 1.2 Use stolen provider key
├── 2. Attribution Evasion [MEDIUM]
│   ├── 2.1 Spoof user/team headers
│   └── 2.2 Use shared/default key
└── 3. Exploit Async Tracking [MEDIUM]
    ├── 3.1 Race condition in spend update
    └── 3.2 Overwhelm tracking pipeline
```

## 6. Security Controls

### 6.1 Preventive Controls
| Control | Threats Mitigated | Implementation |
|---------|-------------------|----------------|
| mTLS | S2, I1 | Istio/Linkerd service mesh |
| Cedar RBAC | E1, E4 | Agent Gateway policies |
| Network Policies | D1, E1 | Kubernetes NetworkPolicy |
| Pod Security Standards | E3 | Restricted PSS profile |
| Input Validation | T1 | LiteLLM guardrails |
| Budget Enforcement | D1 | LiteLLM + Budget Webhook |

### 6.2 Detective Controls
| Control | Threats Detected | Implementation |
|---------|------------------|----------------|
| Audit Logging | R1, R2, R3 | OTel → Loki/Splunk |
| Anomaly Detection | S1, D1 | Prometheus alerts |
| Secret Scanning | I1 | Trivy, Gitleaks |
| Runtime Security | E3, T3 | Falco |

### 6.3 Corrective Controls
| Control | Response | Implementation |
|---------|----------|----------------|
| Key Rotation | Credential compromise | Vault auto-rotate |
| Circuit Breaker | Service degradation | Agent Gateway |
| Auto-scaling | Load spike | KEDA + HPA |
| Incident Runbooks | Security events | PagerDuty integration |

## 7. Risk Register

| Risk ID | Description | Likelihood | Impact | Risk Level | Mitigation Status |
|---------|-------------|------------|--------|-------------|-------------------|
| R-001 | API key exposure via logs | Medium | Critical | HIGH | Mitigated (log scrubbing) |
| R-002 | Cross-tenant data access | Low | Critical | MEDIUM | Mitigated (Cedar policies) |
| R-003 | Budget bypass via direct access | Medium | High | HIGH | Mitigated (NetworkPolicy) |
| R-004 | Prompt injection attacks | High | Medium | HIGH | Partial (guardrails WIP) |
| R-005 | Supply chain compromise | Low | Critical | MEDIUM | Mitigated (image signing) |

## 8. Compliance Mapping

| Requirement | Control | Evidence |
|-------------|---------|----------|
| SOC2 CC6.1 | Access control | Cedar policies, Vault ACLs |
| SOC2 CC6.6 | Encryption | TLS 1.3, Vault encryption |
| SOC2 CC7.2 | Monitoring | OTel traces, Prometheus alerts |
| GDPR Art. 32 | Data protection | Encryption, access logging |
| PCI-DSS 3.4 | Key management | Vault, rotation policies |

## 9. Review and Updates

### 9.1 Review Triggers
- Quarterly scheduled review
- New component addition
- Security incident
- Significant architecture change
- Compliance audit finding

### 9.2 Change Log
| Date | Version | Author | Changes |
|------|---------|--------|---------|
| 2026-02 | 1.0 | Platform Team | Initial threat model |

## Appendix A: DREAD Scoring

| Threat | Damage | Reproducibility | Exploitability | Affected Users | Discoverability | Score |
|--------|--------|-----------------|----------------|----------------|-----------------|-------|
| I1 - Key exposure | 10 | 8 | 6 | 10 | 7 | 8.2 |
| E1 - Cross-tenant | 10 | 5 | 4 | 8 | 3 | 6.0 |
| D1 - Token exhaust | 6 | 9 | 8 | 10 | 8 | 8.2 |
| T1 - Prompt inject | 7 | 8 | 7 | 6 | 9 | 7.4 |
