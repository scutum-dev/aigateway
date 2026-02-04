#!/bin/sh
# Vault initialization script with environment-based secret organization
#
# Usage:
#   ENVIRONMENT=dev ./vault-init.sh      # Initialize dev environment
#   ENVIRONMENT=staging ./vault-init.sh  # Initialize staging environment
#   ENVIRONMENT=production ./vault-init.sh  # Initialize production environment
#
# Required environment variables:
#   OPENAI_API_KEY
#   ANTHROPIC_API_KEY
#   JWT_SECRET
#   LITELLM_MASTER_KEY
#   DATABASE_URL
#
# Optional environment variables:
#   XAI_API_KEY
#   BRAVE_API_KEY
#   GITHUB_TOKEN
#   POSTGRES_PASSWORD
#   GRAFANA_ADMIN_PASSWORD

set -e

# Environment detection
ENVIRONMENT=${ENVIRONMENT:-dev}
VAULT_ADDR=${VAULT_ADDR:-"http://localhost:8200"}
VAULT_TOKEN=${VAULT_TOKEN:-"root-token-for-dev"}

export VAULT_ADDR
export VAULT_TOKEN

# Validate environment
case "$ENVIRONMENT" in
  dev|development)
    ENVIRONMENT="dev"
    VAULT_PATH_PREFIX="secret/ai-gateway/dev"
    ;;
  staging|stg)
    ENVIRONMENT="staging"
    VAULT_PATH_PREFIX="secret/ai-gateway/staging"
    ;;
  prod|production)
    ENVIRONMENT="production"
    VAULT_PATH_PREFIX="secret/ai-gateway/production"
    ;;
  *)
    echo "ERROR: Invalid environment '$ENVIRONMENT'"
    echo "Valid environments: dev, staging, production"
    exit 1
    ;;
esac

echo "=== Initializing Vault for AI Gateway ==="
echo "Environment: $ENVIRONMENT"
echo "Vault Address: $VAULT_ADDR"
echo "Vault Path Prefix: $VAULT_PATH_PREFIX"
echo ""

# Wait for Vault to be ready
echo "Waiting for Vault..."
until vault status > /dev/null 2>&1; do
  sleep 1
done
echo "Vault is ready!"

# Enable KV v2 secrets engine
echo ""
echo "Enabling secrets engine..."
vault secrets enable -path=secret kv-v2 2>/dev/null || echo "Secrets engine already enabled"

# Validate required secrets
echo ""
echo "Validating required secrets..."
MISSING_SECRETS=0

check_required() {
  var_name=$1
  eval var_value=\$$var_name
  if [ -z "$var_value" ]; then
    echo "  ERROR: $var_name is not set (required)"
    MISSING_SECRETS=1
  else
    echo "  OK: $var_name is set"
  fi
}

check_optional() {
  var_name=$1
  eval var_value=\$$var_name
  if [ -z "$var_value" ]; then
    echo "  SKIP: $var_name is not set (optional)"
  else
    echo "  OK: $var_name is set"
  fi
}

# Required secrets
check_required "OPENAI_API_KEY"
check_required "ANTHROPIC_API_KEY"
check_required "JWT_SECRET"
check_required "LITELLM_MASTER_KEY"
check_required "DATABASE_URL"

# Optional secrets
check_optional "XAI_API_KEY"
check_optional "BRAVE_API_KEY"
check_optional "GITHUB_TOKEN"

if [ "$MISSING_SECRETS" -eq 1 ]; then
  echo ""
  echo "ERROR: Missing required secrets. Please set the environment variables listed above."
  echo ""
  echo "Example:"
  echo "  export OPENAI_API_KEY=sk-..."
  echo "  export ANTHROPIC_API_KEY=sk-ant-..."
  echo "  export JWT_SECRET=\$(openssl rand -hex 32)"
  echo "  export LITELLM_MASTER_KEY=sk-litellm-\$(openssl rand -hex 16)"
  echo "  export DATABASE_URL=postgresql://user:pass@host:5432/dbname"
  echo ""
  exit 1
fi

echo ""
echo "Storing secrets in Vault at $VAULT_PATH_PREFIX..."

# Store provider API keys
vault kv put ${VAULT_PATH_PREFIX}/providers/openai \
  api_key="${OPENAI_API_KEY}"
echo "  - OpenAI API key stored"

vault kv put ${VAULT_PATH_PREFIX}/providers/anthropic \
  api_key="${ANTHROPIC_API_KEY}"
echo "  - Anthropic API key stored"

if [ -n "${XAI_API_KEY}" ]; then
  vault kv put ${VAULT_PATH_PREFIX}/providers/xai \
    api_key="${XAI_API_KEY}"
  echo "  - xAI API key stored"
fi

# Store optional provider keys
if [ -n "${BRAVE_API_KEY}" ]; then
  vault kv put ${VAULT_PATH_PREFIX}/providers/brave \
    api_key="${BRAVE_API_KEY}"
  echo "  - Brave Search API key stored"
fi

if [ -n "${GITHUB_TOKEN}" ]; then
  vault kv put ${VAULT_PATH_PREFIX}/providers/github \
    token="${GITHUB_TOKEN}"
  echo "  - GitHub token stored"
fi

# Store application config
vault kv put ${VAULT_PATH_PREFIX}/config/jwt \
  secret="${JWT_SECRET}"
echo "  - JWT secret stored"

vault kv put ${VAULT_PATH_PREFIX}/config/litellm \
  master_key="${LITELLM_MASTER_KEY}"
echo "  - LiteLLM master key stored"

vault kv put ${VAULT_PATH_PREFIX}/config/database \
  url="${DATABASE_URL}"
echo "  - Database URL stored"

# Generate environment-specific passwords if not provided
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-$(openssl rand -hex 16)}
GRAFANA_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:-$(openssl rand -hex 16)}

vault kv put ${VAULT_PATH_PREFIX}/config/postgres \
  password="${POSTGRES_PASSWORD}"
echo "  - Postgres password stored"

vault kv put ${VAULT_PATH_PREFIX}/config/grafana \
  admin_password="${GRAFANA_ADMIN_PASSWORD}"
echo "  - Grafana admin password stored"

# Store environment-specific feature flags
echo ""
echo "Storing feature flags..."

case "$ENVIRONMENT" in
  dev)
    vault kv put ${VAULT_PATH_PREFIX}/config/features \
      debug_mode="true" \
      verbose_logging="true" \
      hot_reload="true" \
      mock_billing="true" \
      rate_limiting="false" \
      tls_enabled="false"
    ;;
  staging)
    vault kv put ${VAULT_PATH_PREFIX}/config/features \
      debug_mode="false" \
      verbose_logging="false" \
      hot_reload="false" \
      mock_billing="false" \
      rate_limiting="true" \
      tls_enabled="true"
    ;;
  production)
    vault kv put ${VAULT_PATH_PREFIX}/config/features \
      debug_mode="false" \
      verbose_logging="false" \
      hot_reload="false" \
      mock_billing="false" \
      rate_limiting="true" \
      tls_enabled="true" \
      high_availability="true" \
      auto_scaling="true"
    ;;
esac
echo "  - Feature flags stored for $ENVIRONMENT"

# Create policies
echo ""
echo "Creating policies..."

# Admin policy - full access
vault policy write admin - <<EOF
path "secret/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
path "sys/*" {
  capabilities = ["create", "read", "update", "delete", "list", "sudo"]
}
path "auth/*" {
  capabilities = ["create", "read", "update", "delete", "list", "sudo"]
}
EOF
echo "  - admin policy created"

# Platform team policy - full access to all environments
vault policy write platform-team - <<EOF
path "secret/data/ai-gateway/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
path "secret/metadata/ai-gateway/*" {
  capabilities = ["list", "read", "delete"]
}
EOF
echo "  - platform-team policy created"

# Environment-specific application policies
for env in dev staging production; do
  vault policy write ai-gateway-${env} - <<EOF
# Read-only access to ${env} environment secrets
path "secret/data/ai-gateway/${env}/providers/*" {
  capabilities = ["read"]
}
path "secret/data/ai-gateway/${env}/config/*" {
  capabilities = ["read"]
}
EOF
  echo "  - ai-gateway-${env} policy created"
done

# ML team policy - read provider keys only
vault policy write ml-team - <<EOF
path "secret/data/ai-gateway/*/providers/*" {
  capabilities = ["read", "list"]
}
path "secret/metadata/ai-gateway/*/providers/*" {
  capabilities = ["list", "read"]
}
EOF
echo "  - ml-team policy created"

# Dev team policy - read dev and staging only
vault policy write dev-team - <<EOF
path "secret/data/ai-gateway/dev/*" {
  capabilities = ["read", "list"]
}
path "secret/data/ai-gateway/staging/*" {
  capabilities = ["read", "list"]
}
path "secret/metadata/ai-gateway/dev/*" {
  capabilities = ["list", "read"]
}
path "secret/metadata/ai-gateway/staging/*" {
  capabilities = ["list", "read"]
}
EOF
echo "  - dev-team policy created"

# Enable authentication methods
echo ""
echo "Enabling authentication methods..."
vault auth enable userpass 2>/dev/null || echo "  userpass already enabled"

# Create environment-specific service accounts
if [ "${VAULT_ENV:-dev}" = "dev" ]; then
  echo "Creating development users..."
  vault write auth/userpass/users/admin \
    password="${VAULT_ADMIN_PASSWORD:-admin-$(openssl rand -hex 8)}" \
    policies="admin"
  echo "  - admin user created"

  vault write auth/userpass/users/platform \
    password="${VAULT_PLATFORM_PASSWORD:-platform-$(openssl rand -hex 8)}" \
    policies="platform-team"
  echo "  - platform user created"
fi

# Enable Kubernetes auth for non-dev environments
if [ "$ENVIRONMENT" != "dev" ]; then
  echo ""
  echo "Enabling Kubernetes authentication..."
  vault auth enable kubernetes 2>/dev/null || echo "  kubernetes auth already enabled"

  # Note: Kubernetes auth requires additional configuration in the cluster
  # This sets up the basic structure, actual K8s config must be done separately
  echo "  NOTE: Configure Kubernetes auth with your cluster credentials"
fi

# Enable audit logging
echo ""
echo "Enabling audit logging..."
vault audit enable file file_path=/vault/logs/audit.log 2>/dev/null || echo "  audit already enabled"

echo ""
echo "=== Vault Setup Complete for $ENVIRONMENT ==="
echo ""
echo "Environment: $ENVIRONMENT"
echo "Vault Path: $VAULT_PATH_PREFIX"
echo ""
echo "Verify secrets:"
echo "  vault kv list ${VAULT_PATH_PREFIX}/"
echo "  vault kv get ${VAULT_PATH_PREFIX}/providers/openai"
echo ""
echo "To retrieve a secret:"
echo "  vault kv get -field=api_key ${VAULT_PATH_PREFIX}/providers/openai"
echo ""
echo "Available service policies:"
echo "  - ai-gateway-dev     (dev environment access)"
echo "  - ai-gateway-staging (staging environment access)"
echo "  - ai-gateway-production (production environment access)"
echo ""
