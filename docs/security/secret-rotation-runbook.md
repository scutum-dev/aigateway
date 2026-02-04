# Secret Rotation Runbook

## Document Information
| Field | Value |
|-------|-------|
| Version | 1.0 |
| Last Updated | 2026-02 |
| Owner | Platform Security Team |
| Review Cycle | Quarterly |

## Overview

This runbook covers rotation procedures for all secrets in the AI Gateway Platform. Secrets are managed in HashiCorp Vault with automatic rotation where possible.

## Secret Inventory

| Secret Type | Location | Rotation Frequency | Auto-Rotate |
|-------------|----------|-------------------|-------------|
| LLM Provider API Keys | Vault `secret/ai-gateway/providers/*` | 90 days | No |
| LiteLLM Master Key | Vault `secret/ai-gateway/litellm/master-key` | 30 days | Yes |
| Database Credentials | Vault `database/creds/litellm` | 24 hours | Yes |
| JWT Signing Key | Vault `secret/ai-gateway/jwt/signing-key` | 7 days | Yes |
| Redis Auth Token | Vault `secret/ai-gateway/redis/auth` | 30 days | Yes |
| TLS Certificates | Cert-Manager | 60 days | Yes |
| Vault Root Token | Vault | Never (use recovery) | N/A |

---

## 1. LLM Provider API Keys

### 1.1 OpenAI API Key Rotation

**Frequency**: Every 90 days or upon suspected compromise

**Prerequisites**:
- Access to OpenAI Platform dashboard
- Vault write access to `secret/ai-gateway/providers/openai`
- `VAULT_ADDR` and `VAULT_TOKEN` environment variables set

**Procedure**:

```bash
#!/bin/bash
# rotate-openai-key.sh
# Run this script to rotate OpenAI API key

set -euo pipefail

VAULT_PATH="secret/ai-gateway/providers/openai"

echo "=== OpenAI API Key Rotation ==="
echo "Started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Step 1: Generate new key in OpenAI dashboard
echo ""
echo "ACTION REQUIRED: Generate new API key at https://platform.openai.com/api-keys"
echo "  1. Click 'Create new secret key'"
echo "  2. Name it: 'ai-gateway-prod-$(date +%Y%m%d)'"
echo "  3. Copy the key (you won't see it again)"
echo ""
read -p "Enter new OpenAI API key: " NEW_KEY

# Validate key format
if [[ ! "$NEW_KEY" =~ ^sk-[a-zA-Z0-9]{48,}$ ]]; then
    echo "ERROR: Invalid key format. OpenAI keys start with 'sk-'"
    exit 1
fi

# Step 2: Store old key for rollback
echo "Backing up current key..."
OLD_KEY=$(vault kv get -field=api_key "$VAULT_PATH" 2>/dev/null || echo "")
if [ -n "$OLD_KEY" ]; then
    vault kv put "${VAULT_PATH}-backup" \
        api_key="$OLD_KEY" \
        rotated_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        reason="scheduled_rotation"
fi

# Step 3: Write new key to Vault
echo "Writing new key to Vault..."
vault kv put "$VAULT_PATH" \
    api_key="$NEW_KEY" \
    rotated_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    rotated_by="$USER"

# Step 4: Trigger secret refresh in pods
echo "Triggering pod secret refresh..."
kubectl rollout restart deployment/litellm -n ai-gateway

# Step 5: Verify new key works
echo "Waiting for rollout..."
kubectl rollout status deployment/litellm -n ai-gateway --timeout=300s

echo "Testing new key..."
sleep 10  # Allow for startup
RESPONSE=$(curl -sf -X POST https://api.openai.com/v1/chat/completions \
    -H "Authorization: Bearer $NEW_KEY" \
    -H "Content-Type: application/json" \
    -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"test"}],"max_tokens":1}' \
    2>&1 || echo "FAILED")

if echo "$RESPONSE" | grep -q "choices"; then
    echo "✓ New key verified successfully"
else
    echo "✗ Key verification failed!"
    echo "Rolling back..."
    vault kv put "$VAULT_PATH" api_key="$OLD_KEY"
    kubectl rollout restart deployment/litellm -n ai-gateway
    exit 1
fi

# Step 6: Revoke old key
echo ""
echo "ACTION REQUIRED: Revoke old API key in OpenAI dashboard"
echo "  1. Go to https://platform.openai.com/api-keys"
echo "  2. Find the previous key (check last used date)"
echo "  3. Click delete/revoke"
read -p "Press Enter after revoking old key..."

echo ""
echo "=== Rotation Complete ==="
echo "Completed: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

### 1.2 Anthropic API Key Rotation

**Frequency**: Every 90 days or upon suspected compromise

```bash
#!/bin/bash
# rotate-anthropic-key.sh

set -euo pipefail

VAULT_PATH="secret/ai-gateway/providers/anthropic"

echo "=== Anthropic API Key Rotation ==="

echo "ACTION REQUIRED: Generate new API key at https://console.anthropic.com/settings/keys"
read -p "Enter new Anthropic API key: " NEW_KEY

if [[ ! "$NEW_KEY" =~ ^sk-ant-[a-zA-Z0-9-]{40,}$ ]]; then
    echo "ERROR: Invalid key format. Anthropic keys start with 'sk-ant-'"
    exit 1
fi

# Backup and rotate
OLD_KEY=$(vault kv get -field=api_key "$VAULT_PATH" 2>/dev/null || echo "")
[ -n "$OLD_KEY" ] && vault kv put "${VAULT_PATH}-backup" api_key="$OLD_KEY" rotated_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

vault kv put "$VAULT_PATH" \
    api_key="$NEW_KEY" \
    rotated_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    rotated_by="$USER"

# Restart and verify
kubectl rollout restart deployment/litellm -n ai-gateway
kubectl rollout status deployment/litellm -n ai-gateway --timeout=300s

echo "Testing..."
sleep 10
RESPONSE=$(curl -sf -X POST https://api.anthropic.com/v1/messages \
    -H "x-api-key: $NEW_KEY" \
    -H "anthropic-version: 2023-06-01" \
    -H "Content-Type: application/json" \
    -d '{"model":"claude-3-haiku-20240307","max_tokens":1,"messages":[{"role":"user","content":"test"}]}' \
    2>&1 || echo "FAILED")

if echo "$RESPONSE" | grep -q "content"; then
    echo "✓ Rotation successful"
else
    echo "✗ Verification failed - rolling back"
    vault kv put "$VAULT_PATH" api_key="$OLD_KEY"
    kubectl rollout restart deployment/litellm -n ai-gateway
    exit 1
fi

echo "ACTION REQUIRED: Revoke old key at https://console.anthropic.com/settings/keys"
```

### 1.3 XAI (Grok) API Key Rotation

```bash
#!/bin/bash
# rotate-xai-key.sh

set -euo pipefail

VAULT_PATH="secret/ai-gateway/providers/xai"

echo "=== XAI API Key Rotation ==="

echo "ACTION REQUIRED: Generate new API key at https://console.x.ai/team/api-keys"
read -p "Enter new XAI API key: " NEW_KEY

if [[ ! "$NEW_KEY" =~ ^xai-[a-zA-Z0-9]{40,}$ ]]; then
    echo "ERROR: Invalid key format. XAI keys start with 'xai-'"
    exit 1
fi

OLD_KEY=$(vault kv get -field=api_key "$VAULT_PATH" 2>/dev/null || echo "")
[ -n "$OLD_KEY" ] && vault kv put "${VAULT_PATH}-backup" api_key="$OLD_KEY" rotated_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

vault kv put "$VAULT_PATH" \
    api_key="$NEW_KEY" \
    rotated_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    rotated_by="$USER"

kubectl rollout restart deployment/litellm -n ai-gateway
kubectl rollout status deployment/litellm -n ai-gateway --timeout=300s

echo "✓ XAI key rotated. Verify via LiteLLM health check."
```

---

## 2. Database Credentials (Automatic)

Database credentials are automatically rotated by Vault's database secrets engine.

### 2.1 Setup (One-time)

```bash
# Enable database secrets engine
vault secrets enable database

# Configure PostgreSQL connection
vault write database/config/litellm \
    plugin_name=postgresql-database-plugin \
    allowed_roles="litellm-app,litellm-readonly" \
    connection_url="postgresql://{{username}}:{{password}}@postgres:5432/litellm?sslmode=require" \
    username="vault_admin" \
    password="$VAULT_DB_PASSWORD"

# Create application role (24-hour TTL)
vault write database/roles/litellm-app \
    db_name=litellm \
    creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; \
        GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO \"{{name}}\"; \
        GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO \"{{name}}\";" \
    default_ttl="24h" \
    max_ttl="48h"

# Create readonly role for reporting
vault write database/roles/litellm-readonly \
    db_name=litellm \
    creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; \
        GRANT SELECT ON ALL TABLES IN SCHEMA public TO \"{{name}}\";" \
    default_ttl="1h" \
    max_ttl="4h"
```

### 2.2 Application Usage

Applications request credentials via Vault Agent Injector:

```yaml
# Pod annotation for automatic credential injection
annotations:
  vault.hashicorp.com/agent-inject: "true"
  vault.hashicorp.com/role: "litellm-app"
  vault.hashicorp.com/agent-inject-secret-db-creds: "database/creds/litellm-app"
  vault.hashicorp.com/agent-inject-template-db-creds: |
    {{- with secret "database/creds/litellm-app" -}}
    export DATABASE_URL="postgresql://{{ .Data.username }}:{{ .Data.password }}@postgres:5432/litellm"
    {{- end }}
```

### 2.3 Manual Rotation (Emergency)

```bash
# Force immediate credential rotation
vault lease revoke -prefix database/creds/litellm-app

# Pods will automatically get new credentials on next renewal
```

---

## 3. JWT Signing Key

### 3.1 Automatic Rotation Setup

```bash
# Enable transit secrets engine
vault secrets enable transit

# Create signing key with automatic rotation
vault write transit/keys/jwt-signing \
    type=rsa-4096 \
    auto_rotate_period=168h  # 7 days
```

### 3.2 Manual Rotation (Emergency)

```bash
#!/bin/bash
# rotate-jwt-key.sh

echo "=== JWT Signing Key Rotation ==="

# Rotate key (creates new version, old versions still valid for verification)
vault write -f transit/keys/jwt-signing/rotate

# Get new key version
NEW_VERSION=$(vault read -field=latest_version transit/keys/jwt-signing)
echo "New key version: $NEW_VERSION"

# Optionally disable old versions after grace period
echo "Old tokens will remain valid until they expire"
echo "To force invalidation, set min_decryption_version:"
echo "  vault write transit/keys/jwt-signing/config min_decryption_version=$NEW_VERSION"
```

---

## 4. LiteLLM Master Key

### 4.1 Rotation Procedure

```bash
#!/bin/bash
# rotate-litellm-master-key.sh

set -euo pipefail

VAULT_PATH="secret/ai-gateway/litellm/master-key"

echo "=== LiteLLM Master Key Rotation ==="

# Generate new secure key
NEW_KEY="sk-litellm-$(openssl rand -hex 24)"
echo "Generated new master key"

# Backup old key
OLD_KEY=$(vault kv get -field=key "$VAULT_PATH" 2>/dev/null || echo "")
[ -n "$OLD_KEY" ] && vault kv put "${VAULT_PATH}-backup" key="$OLD_KEY" rotated_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Store new key
vault kv put "$VAULT_PATH" \
    key="$NEW_KEY" \
    rotated_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Update Kubernetes secret
kubectl create secret generic litellm-master-key \
    --from-literal=key="$NEW_KEY" \
    --dry-run=client -o yaml | kubectl apply -f -

# Restart LiteLLM
kubectl rollout restart deployment/litellm -n ai-gateway
kubectl rollout status deployment/litellm -n ai-gateway --timeout=300s

# Verify
sleep 10
HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' \
    -H "Authorization: Bearer $NEW_KEY" \
    http://localhost:4000/health)

if [ "$HTTP_CODE" = "200" ]; then
    echo "✓ Master key rotation successful"
    echo ""
    echo "IMPORTANT: Update all client configurations with new key"
    echo "New key: $NEW_KEY"
else
    echo "✗ Rotation failed, rolling back"
    vault kv put "$VAULT_PATH" key="$OLD_KEY"
    kubectl create secret generic litellm-master-key \
        --from-literal=key="$OLD_KEY" \
        --dry-run=client -o yaml | kubectl apply -f -
    kubectl rollout restart deployment/litellm -n ai-gateway
    exit 1
fi
```

---

## 5. TLS Certificates (Automatic)

TLS certificates are managed by cert-manager with automatic renewal.

### 5.1 Setup

```yaml
# Certificate resource (auto-renews 30 days before expiry)
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: ai-gateway-tls
  namespace: ai-gateway
spec:
  secretName: ai-gateway-tls
  duration: 2160h    # 90 days
  renewBefore: 720h  # 30 days
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
    - gateway.example.com
    - api.gateway.example.com
```

### 5.2 Manual Renewal (Emergency)

```bash
# Force certificate renewal
kubectl delete secret ai-gateway-tls -n ai-gateway
# cert-manager will automatically issue new certificate

# Or trigger renewal via annotation
kubectl annotate certificate ai-gateway-tls -n ai-gateway \
    cert-manager.io/issuer-name=letsencrypt-prod --overwrite
```

---

## 6. Emergency Response

### 6.1 Suspected Key Compromise

```bash
#!/bin/bash
# emergency-key-revoke.sh

echo "=== EMERGENCY KEY REVOCATION ==="
echo "Provider: $1"

case "$1" in
    openai)
        echo "1. Immediately revoke key at https://platform.openai.com/api-keys"
        echo "2. Run: ./rotate-openai-key.sh"
        ;;
    anthropic)
        echo "1. Immediately revoke key at https://console.anthropic.com/settings/keys"
        echo "2. Run: ./rotate-anthropic-key.sh"
        ;;
    xai)
        echo "1. Immediately revoke key at https://console.x.ai"
        echo "2. Run: ./rotate-xai-key.sh"
        ;;
    litellm)
        echo "Running immediate master key rotation..."
        ./rotate-litellm-master-key.sh
        ;;
    database)
        echo "Revoking all database credentials..."
        vault lease revoke -prefix database/creds/
        kubectl rollout restart deployment -n ai-gateway
        ;;
    *)
        echo "Unknown provider. Manual intervention required."
        ;;
esac

echo ""
echo "Post-incident actions:"
echo "1. Review audit logs: vault audit list"
echo "2. Check for unauthorized usage in Grafana"
echo "3. File incident report"
```

### 6.2 Full Secret Rotation (Nuclear Option)

```bash
#!/bin/bash
# rotate-all-secrets.sh

echo "=== FULL SECRET ROTATION ==="
echo "This will rotate ALL secrets. Continue? (yes/no)"
read CONFIRM
[ "$CONFIRM" != "yes" ] && exit 1

./rotate-openai-key.sh
./rotate-anthropic-key.sh
./rotate-xai-key.sh
./rotate-litellm-master-key.sh
./rotate-jwt-key.sh

vault lease revoke -prefix database/creds/

kubectl rollout restart deployment -n ai-gateway

echo "=== All secrets rotated ==="
```

---

## 7. Monitoring and Alerts

### 7.1 Prometheus Alerts

```yaml
groups:
  - name: secret-rotation
    rules:
      - alert: SecretRotationOverdue
        expr: |
          (time() - vault_secret_rotation_timestamp{path=~"secret/ai-gateway/providers/.*"}) > 86400 * 90
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "Secret rotation overdue for {{ $labels.path }}"

      - alert: VaultLeaseExpiringSoon
        expr: vault_lease_ttl_seconds < 3600
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Vault lease expiring in < 1 hour"
```

### 7.2 Audit Log Queries

```bash
# Recent secret accesses
vault audit | grep "secret/ai-gateway" | tail -100

# Failed authentication attempts
vault audit | grep "response.*error" | tail -50

# Secret reads by user
vault audit | grep "read.*secret/ai-gateway" | jq '.auth.display_name'
```

---

## Appendix: Rotation Schedule

| Month | Week 1 | Week 2 | Week 3 | Week 4 |
|-------|--------|--------|--------|--------|
| Jan | JWT | - | - | LiteLLM Master |
| Feb | JWT | - | - | LiteLLM Master |
| Mar | JWT | OpenAI | - | LiteLLM Master |
| Apr | JWT | - | Anthropic | LiteLLM Master |
| May | JWT | - | - | LiteLLM Master |
| Jun | JWT | OpenAI | XAI | LiteLLM Master |
| ... | ... | ... | ... | ... |
