#!/bin/bash
# Seed demo data by making real LLM API calls
# Called by Terraform after cluster deployment

set -e

GATEWAY_URL="${GATEWAY_URL:-http://gateway.deos.dev:4000}"
LITELLM_KEY="${LITELLM_MASTER_KEY:-sk-litellm-demo-key}"

echo "=== Seeding Demo Data via Real API Calls ==="
echo "Gateway: $GATEWAY_URL"

# Wait for LiteLLM to be ready
wait_for_litellm() {
    local max_attempts=30
    local attempt=1
    echo -n "Waiting for LiteLLM"
    while [ $attempt -le $max_attempts ]; do
        if curl -s -f "${GATEWAY_URL}/health/readiness" > /dev/null 2>&1; then
            echo " ready!"
            return 0
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    echo " timeout!"
    exit 1
}

wait_for_litellm

# Make real LLM requests to generate actual usage/cost data
make_request() {
    local model=$1
    local prompt=$2
    local user=$3
    local team=$4

    response=$(curl -s -w "\n%{http_code}" -X POST "${GATEWAY_URL}/v1/chat/completions" \
        -H "Authorization: Bearer $LITELLM_KEY" \
        -H "Content-Type: application/json" \
        -d "{
            \"model\": \"$model\",
            \"messages\": [{\"role\": \"user\", \"content\": \"$prompt\"}],
            \"max_tokens\": 100,
            \"user\": \"$user\",
            \"metadata\": {\"team_id\": \"$team\"}
        }" 2>/dev/null)

    http_code=$(echo "$response" | tail -1)
    if [ "$http_code" = "200" ]; then
        echo "  [OK] $model ($user/$team)"
        return 0
    else
        echo "  [SKIP] $model - not configured or unavailable"
        return 1
    fi
}

echo ""
echo "=== Making Real LLM Requests ==="

# Engineering team requests
echo "Engineering team:"
make_request "gpt-4o-mini" "Explain what a Kubernetes pod is in 2 sentences." "eng-user-1" "engineering" || true
make_request "gpt-4o-mini" "What is the difference between a container and a VM?" "eng-user-1" "engineering" || true
make_request "gpt-4o-mini" "List 3 benefits of microservices architecture." "eng-user-2" "engineering" || true
make_request "claude-3-haiku" "What is infrastructure as code?" "eng-user-1" "engineering" || true

# Data science team requests
echo "Data science team:"
make_request "gpt-4o" "Explain gradient descent in simple terms." "ds-user-1" "data-science" || true
make_request "gpt-4o" "What are the main types of machine learning?" "ds-user-1" "data-science" || true
make_request "claude-sonnet-4.5" "Compare random forests and gradient boosting." "ds-user-2" "data-science" || true

# Product team requests
echo "Product team:"
make_request "gpt-4o-mini" "What makes a good product requirements document?" "pm-user-1" "product" || true
make_request "claude-haiku-4.5" "List 5 key metrics for SaaS products." "pm-user-1" "product" || true

# Grok requests (if available)
echo "Testing Grok:"
make_request "grok-3" "What is the current state of AI?" "eng-user-1" "engineering" || true

echo ""
echo "=== Verifying Generated Data ==="

# Check spend logs
echo "Spend data:"
curl -s "${GATEWAY_URL}/spend/logs?limit=5" \
    -H "Authorization: Bearer $LITELLM_KEY" 2>/dev/null | \
    jq -r '.[] | "  \(.user // "unknown"): \(.model) - $\(.spend // 0)"' 2>/dev/null || echo "  Spend tracking may be disabled"

echo ""
echo "=== Demo data seeded from real API calls ==="
