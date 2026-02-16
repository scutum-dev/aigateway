#!/bin/bash
# Comprehensive test script for AI Control Plane Platform
# Tests all features: LLM routing, cost tracking, Vault, etc.
# Works without vault CLI - uses curl API calls

# Don't exit on errors - we want to run all tests
# set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
LITELLM_URL=${LITELLM_URL:-"http://localhost:4000"}
VAULT_URL=${VAULT_URL:-"http://localhost:8200"}
VAULT_TOKEN=${VAULT_TOKEN:-"root-token-for-dev"}
COST_PREDICTOR_URL=${COST_PREDICTOR_URL:-"http://localhost:8080"}
FINOPS_URL=${FINOPS_URL:-"http://localhost:8082"}
# Agent Gateway now serves all protocols on port 9000 (mapped to internal 3000)
MCP_GATEWAY_URL=${MCP_GATEWAY_URL:-"http://localhost:9000"}
A2A_GATEWAY_URL=${A2A_GATEWAY_URL:-"http://localhost:9000"}
AGENTGATEWAY_URL=${AGENTGATEWAY_URL:-"http://localhost:9000"}
API_KEY=${API_KEY:-"$LITELLM_KEY"}

# Test counters
PASSED=0
FAILED=0
SKIPPED=0

# Test function
run_test() {
  local name=$1
  local cmd=$2

  printf "  %-50s " "$name"

  if result=$(eval "$cmd" 2>&1); then
    echo -e "${GREEN}✓ PASSED${NC}"
    ((PASSED++))
    return 0
  else
    echo -e "${RED}✗ FAILED${NC}"
    echo -e "    ${RED}Error: $result${NC}"
    ((FAILED++))
    return 1
  fi
}

skip_test() {
  local name=$1
  local reason=$2
  printf "  %-50s " "$name"
  echo -e "${YELLOW}○ SKIPPED${NC} ($reason)"
  ((SKIPPED++))
}

echo ""
echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}           AI Control Plane Platform - Test Suite                   ${NC}"
echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
echo ""

# ===========================================
# Health Checks
# ===========================================
echo -e "${BLUE}--- Health Checks ---${NC}"

run_test "LiteLLM health" \
  "curl -sf ${LITELLM_URL}/health -H 'Authorization: Bearer ${API_KEY}' | grep -q 'healthy'"

run_test "Vault health" \
  "curl -sf ${VAULT_URL}/v1/sys/health | grep -q 'initialized'"

run_test "Cost Predictor health" \
  "curl -sf ${COST_PREDICTOR_URL}/health | grep -q 'healthy'" || \
  skip_test "Cost Predictor health" "service not running"

run_test "FinOps Reporter health" \
  "curl -sf ${FINOPS_URL}/health | grep -q 'healthy'" || \
  skip_test "FinOps Reporter health" "service not running"

# Agent Gateway MCP returns "Not Acceptable" or "Session ID" when working
run_test "Agent Gateway running" \
  "curl -s ${AGENTGATEWAY_URL}/ 2>&1 | grep -qE '(Session|Acceptable|event-stream)'"

run_test "Budget Webhook health" \
  "curl -sf http://localhost:8081/health | grep -q 'healthy'" || \
  skip_test "Budget Webhook health" "service not running"

run_test "PostgreSQL health" \
  "curl -sf http://localhost:5432 2>&1 | grep -q '' || docker exec postgres pg_isready -U postgres > /dev/null 2>&1" || \
  skip_test "PostgreSQL health" "service not running"

run_test "Redis health" \
  "docker exec redis redis-cli ping 2>/dev/null | grep -q 'PONG'" || \
  skip_test "Redis health" "service not running"

echo ""

# ===========================================
# Vault Tests (using API, no CLI needed)
# ===========================================
echo -e "${BLUE}--- Vault Tests ---${NC}"

run_test "Vault secrets engine accessible" \
  "curl -sf -H 'X-Vault-Token: ${VAULT_TOKEN}' ${VAULT_URL}/v1/secret/data/ai-gateway/providers/openai | grep -q 'api_key'"

run_test "OpenAI key stored in Vault" \
  "curl -sf -H 'X-Vault-Token: ${VAULT_TOKEN}' ${VAULT_URL}/v1/secret/data/ai-gateway/providers/openai | grep -q 'sk-'"

run_test "Anthropic key stored in Vault" \
  "curl -sf -H 'X-Vault-Token: ${VAULT_TOKEN}' ${VAULT_URL}/v1/secret/data/ai-gateway/providers/anthropic | grep -q 'sk-ant'"

run_test "XAI key stored in Vault" \
  "curl -sf -H 'X-Vault-Token: ${VAULT_TOKEN}' ${VAULT_URL}/v1/secret/data/ai-gateway/providers/xai | grep -q 'xai-'"

run_test "Brave API key stored in Vault" \
  "curl -sf -H 'X-Vault-Token: ${VAULT_TOKEN}' ${VAULT_URL}/v1/secret/data/ai-gateway/providers/brave | grep -q 'api_key'" || \
  skip_test "Brave API key stored in Vault" "not configured"

echo ""

# ===========================================
# LiteLLM Model Tests
# ===========================================
echo -e "${BLUE}--- LLM Provider Tests ---${NC}"

run_test "List models endpoint" \
  "curl -sf -H 'Authorization: Bearer ${API_KEY}' ${LITELLM_URL}/v1/models | grep -q 'gpt-4o'"

run_test "OpenAI GPT-4o-mini request" \
  "curl -sf -X POST ${LITELLM_URL}/v1/chat/completions \
    -H 'Authorization: Bearer ${API_KEY}' \
    -H 'Content-Type: application/json' \
    -d '{\"model\": \"gpt-4o-mini\", \"messages\": [{\"role\": \"user\", \"content\": \"Say test\"}], \"max_tokens\": 5}' \
    | grep -q 'choices'"

run_test "Anthropic Claude 3 Haiku request" \
  "curl -sf -X POST ${LITELLM_URL}/v1/chat/completions \
    -H 'Authorization: Bearer ${API_KEY}' \
    -H 'Content-Type: application/json' \
    -d '{\"model\": \"claude-3-haiku\", \"messages\": [{\"role\": \"user\", \"content\": \"Say test\"}], \"max_tokens\": 5}' \
    | grep -q 'choices'"

run_test "XAI Grok-3 request" \
  "curl -sf -X POST ${LITELLM_URL}/v1/chat/completions \
    -H 'Authorization: Bearer ${API_KEY}' \
    -H 'Content-Type: application/json' \
    -d '{\"model\": \"grok-3\", \"messages\": [{\"role\": \"user\", \"content\": \"Say test\"}], \"max_tokens\": 5}' \
    | grep -q 'choices'"

echo ""

# ===========================================
# Nginx Routing Tests (Unified Gateway)
# ===========================================
echo -e "${BLUE}--- Nginx Routing Tests ---${NC}"

NGINX_URL=${NGINX_URL:-"http://localhost"}

run_test "Nginx health" \
  "curl -sf ${NGINX_URL}/health | grep -q 'OK'" || \
  skip_test "Nginx health" "Nginx not running"

if curl -sf ${NGINX_URL}/health > /dev/null 2>&1; then
  run_test "LLM via Nginx (/v1/models)" \
    "curl -sf -H 'Authorization: Bearer ${API_KEY}' ${NGINX_URL}/v1/models | grep -q 'gpt-4o'"

  run_test "MCP via Nginx (/mcp/)" \
    "curl -s -H 'Accept: text/event-stream' ${NGINX_URL}/mcp/ 2>&1 | grep -qE '(Session|session)'"
else
  skip_test "LLM via Nginx (/v1/models)" "Nginx not running"
  skip_test "MCP via Nginx (/mcp/)" "Nginx not running"
fi

echo ""

# ===========================================
# Cost Tracking Tests
# ===========================================
echo -e "${BLUE}--- Cost Tracking Tests ---${NC}"

run_test "Usage tokens in response" \
  "curl -sf -X POST ${LITELLM_URL}/v1/chat/completions \
    -H 'Authorization: Bearer ${API_KEY}' \
    -H 'Content-Type: application/json' \
    -d '{\"model\": \"gpt-4o-mini\", \"messages\": [{\"role\": \"user\", \"content\": \"Hi\"}], \"max_tokens\": 5}' \
    | grep -q 'total_tokens'"

if curl -sf ${COST_PREDICTOR_URL}/health > /dev/null 2>&1; then
  run_test "Cost prediction endpoint" \
    "curl -sf -X POST ${COST_PREDICTOR_URL}/predict \
      -H 'Content-Type: application/json' \
      -d '{\"model\": \"gpt-4o-mini\", \"messages\": [{\"role\": \"user\", \"content\": \"Hello\"}], \"max_tokens\": 100}' \
      | grep -q 'total_estimated_cost'"

  run_test "Pricing endpoint" \
    "curl -sf ${COST_PREDICTOR_URL}/pricing | grep -q 'gpt-4o'"
else
  skip_test "Cost prediction endpoint" "service not running"
  skip_test "Pricing endpoint" "service not running"
fi

echo ""

# ===========================================
# Streaming Tests
# ===========================================
echo -e "${BLUE}--- Streaming Tests ---${NC}"

run_test "Streaming response" \
  "curl -sf -X POST ${LITELLM_URL}/v1/chat/completions \
    -H 'Authorization: Bearer ${API_KEY}' \
    -H 'Content-Type: application/json' \
    -d '{\"model\": \"gpt-4o-mini\", \"messages\": [{\"role\": \"user\", \"content\": \"Count 1 to 3\"}], \"max_tokens\": 20, \"stream\": true}' \
    | grep -q 'data:'"

echo ""

# ===========================================
# FinOps Reporter Tests
# ===========================================
echo -e "${BLUE}--- FinOps Reporter Tests ---${NC}"

if curl -sf ${FINOPS_URL}/health > /dev/null 2>&1; then
  run_test "Summary stats endpoint" \
    "curl -sf ${FINOPS_URL}/reports/summary | grep -q 'today'"

  run_test "Cost report endpoint" \
    "curl -sf '${FINOPS_URL}/reports/cost?period=daily' | grep -q 'total_cost'"
else
  skip_test "Summary stats endpoint" "service not running"
  skip_test "Cost report endpoint" "service not running"
fi

echo ""

# ===========================================
# MCP Gateway Tests
# ===========================================
echo -e "${BLUE}--- MCP Gateway Tests ---${NC}"

# Agent Gateway MCP returns "Session ID is required" or "Not Acceptable" when working
run_test "MCP endpoint responds" \
  "curl -s ${MCP_GATEWAY_URL}/ 2>&1 | grep -qE '(Session|Acceptable)'"

run_test "MCP with SSE header" \
  "curl -s -H 'Accept: text/event-stream' ${MCP_GATEWAY_URL}/ 2>&1 | grep -qE '(Session|session)'"

# Note: Full MCP testing requires proper SSE client with session management
skip_test "MCP tools discovery" "requires SSE client"
skip_test "MCP filesystem tools" "requires SSE client"

echo ""

# ===========================================
# A2A Gateway Tests
# ===========================================
echo -e "${BLUE}--- A2A Gateway Tests ---${NC}"

# A2A requires agent configuration - skip for now if not configured
skip_test "A2A agent discovery" "A2A agents not configured"
skip_test "A2A agent communication" "A2A agents not configured"

echo -e "  ${YELLOW}Note: A2A requires agent deployments to be configured${NC}"

echo ""

# ===========================================
# Error Handling Tests
# ===========================================
echo -e "${BLUE}--- Error Handling Tests ---${NC}"

run_test "Invalid model returns error" \
  "curl -s -X POST ${LITELLM_URL}/v1/chat/completions \
    -H 'Authorization: Bearer ${API_KEY}' \
    -H 'Content-Type: application/json' \
    -d '{\"model\": \"nonexistent-model-xyz\", \"messages\": [{\"role\": \"user\", \"content\": \"Hi\"}]}' \
    | grep -qE '(error|Error)'"

run_test "Missing auth returns 401" \
  "curl -s -o /dev/null -w '%{http_code}' ${LITELLM_URL}/v1/models | grep -q '401'"

echo ""

# ===========================================
# Observability Tests
# ===========================================
echo -e "${BLUE}--- Observability Tests ---${NC}"

run_test "Prometheus health" \
  "curl -sf http://localhost:9090/-/healthy | grep -qE '(Healthy|OK)'" || \
  skip_test "Prometheus health" "service not running"

run_test "Grafana health" \
  "curl -sf http://localhost:3030/api/health | grep -q 'ok'" || \
  skip_test "Grafana health" "service not running"

run_test "Jaeger health" \
  "curl -sf http://localhost:16686/ > /dev/null 2>&1" || \
  skip_test "Jaeger health" "service not running"

# OTEL Collector - check if it's accepting connections on metrics port
run_test "OTEL Collector running" \
  "curl -s http://localhost:8889/metrics 2>&1 | grep -qE '(otel|collector)'" || \
  skip_test "OTEL Collector running" "service not running"

echo ""

# ===========================================
# Summary
# ===========================================
echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}                      Test Summary                            ${NC}"
echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${GREEN}Passed:${NC}  $PASSED"
echo -e "  ${RED}Failed:${NC}  $FAILED"
echo -e "  ${YELLOW}Skipped:${NC} $SKIPPED"
echo ""

if [ $FAILED -eq 0 ]; then
  echo -e "${GREEN}✓ All tests passed!${NC}"
  echo ""
  exit 0
else
  echo -e "${RED}✗ Some tests failed!${NC}"
  echo ""
  exit 1
fi
