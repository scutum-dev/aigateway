#!/bin/bash
# Seed demo data for the AI Control Plane
# Called by Terraform after cluster deployment, or manually via: ./scripts/seed-demo-data.sh

set -e

GATEWAY_URL="${GATEWAY_URL:-http://api.aicontrolplane.dev}"
LITELLM_KEY="${LITELLM_MASTER_KEY:-sk-litellm-demo-key}"
ADMIN_TOKEN=""

echo "=== Seeding Demo Data ==="
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

# Get admin JWT token
get_admin_token() {
    echo -n "Getting admin token... "
    local response
    response=$(curl -s -X POST "${GATEWAY_URL}/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"api_key\": \"$LITELLM_KEY\"}" 2>/dev/null)

    ADMIN_TOKEN=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)

    if [ -z "$ADMIN_TOKEN" ]; then
        echo "FAILED (will skip admin-api seeding)"
        return 1
    fi
    echo "OK"
    return 0
}

# Helper: POST to admin API
admin_post() {
    local path=$1
    local data=$2
    local response
    response=$(curl -s -w "\n%{http_code}" -X POST "${GATEWAY_URL}${path}" \
        -H "Authorization: Bearer $ADMIN_TOKEN" \
        -H "Content-Type: application/json" \
        -d "$data" 2>/dev/null)
    local http_code
    http_code=$(echo "$response" | tail -1)
    if [ "$http_code" = "200" ] || [ "$http_code" = "201" ]; then
        echo "  [OK] POST $path"
        return 0
    else
        echo "  [SKIP] POST $path ($http_code)"
        return 1
    fi
}

# Make real LLM requests to generate usage/cost data
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

wait_for_litellm
get_admin_token || true

# =========================================================================
# 1. API Keys (via LiteLLM directly)
# =========================================================================
echo ""
echo "=== Seeding API Keys ==="

# Generate team-scoped keys
curl -s -X POST "${GATEWAY_URL}/key/generate" \
    -H "Authorization: Bearer $LITELLM_KEY" \
    -H "Content-Type: application/json" \
    -d '{
        "key_alias": "eng-backend-prod",
        "max_budget": 50.0,
        "models": ["gpt-4o-mini", "gpt-4o", "claude-haiku-4.5"],
        "metadata": {"team": "engineering", "env": "production"},
        "duration": "90d"
    }' > /dev/null 2>&1 && echo "  [OK] Key: eng-backend-prod" || echo "  [SKIP] eng-backend-prod"

curl -s -X POST "${GATEWAY_URL}/key/generate" \
    -H "Authorization: Bearer $LITELLM_KEY" \
    -H "Content-Type: application/json" \
    -d '{
        "key_alias": "eng-frontend-staging",
        "max_budget": 10.0,
        "models": ["gpt-4o-mini"],
        "metadata": {"team": "engineering", "env": "staging"},
        "duration": "30d"
    }' > /dev/null 2>&1 && echo "  [OK] Key: eng-frontend-staging" || echo "  [SKIP] eng-frontend-staging"

curl -s -X POST "${GATEWAY_URL}/key/generate" \
    -H "Authorization: Bearer $LITELLM_KEY" \
    -H "Content-Type: application/json" \
    -d '{
        "key_alias": "ds-notebooks",
        "max_budget": 200.0,
        "models": ["gpt-4o", "claude-sonnet-4-5-20250929", "claude-opus-4-6"],
        "metadata": {"team": "data-science", "env": "production"},
        "duration": "365d"
    }' > /dev/null 2>&1 && echo "  [OK] Key: ds-notebooks" || echo "  [SKIP] ds-notebooks"

curl -s -X POST "${GATEWAY_URL}/key/generate" \
    -H "Authorization: Bearer $LITELLM_KEY" \
    -H "Content-Type: application/json" \
    -d '{
        "key_alias": "product-copilot",
        "max_budget": 25.0,
        "metadata": {"team": "product", "env": "production"},
        "duration": "60d"
    }' > /dev/null 2>&1 && echo "  [OK] Key: product-copilot" || echo "  [SKIP] product-copilot"

curl -s -X POST "${GATEWAY_URL}/key/generate" \
    -H "Authorization: Bearer $LITELLM_KEY" \
    -H "Content-Type: application/json" \
    -d '{
        "key_alias": "ci-cd-pipeline",
        "max_budget": 5.0,
        "models": ["gpt-4o-mini"],
        "metadata": {"team": "devops", "env": "ci"}
    }' > /dev/null 2>&1 && echo "  [OK] Key: ci-cd-pipeline" || echo "  [SKIP] ci-cd-pipeline"

# =========================================================================
# 2. Teams & Members (via Admin API)
# =========================================================================
if [ -n "$ADMIN_TOKEN" ]; then
    echo ""
    echo "=== Seeding Teams ==="

    admin_post "/api/v1/teams" '{
        "name": "devops",
        "description": "DevOps & Infrastructure team",
        "monthly_budget": 150.0,
        "default_model": "gpt-4o-mini"
    }' || true

    admin_post "/api/v1/teams" '{
        "name": "security",
        "description": "Security & Compliance team",
        "monthly_budget": 100.0,
        "default_model": "gpt-4o"
    }' || true

    # Add members to teams (look up team UUIDs by name)
    echo "Adding team members..."
    TEAMS_JSON=$(curl -s "${GATEWAY_URL}/api/v1/teams" -H "Authorization: Bearer $ADMIN_TOKEN" 2>/dev/null)
    get_team_id() {
        echo "$TEAMS_JSON" | python3 -c "import sys,json; teams=json.load(sys.stdin); print(next((t['id'] for t in teams if t['name']=='$1'),''))" 2>/dev/null
    }

    ENG_ID=$(get_team_id engineering)
    DS_ID=$(get_team_id data-science)
    PROD_ID=$(get_team_id product)

    if [ -n "$ENG_ID" ]; then
        admin_post "/api/v1/teams/${ENG_ID}/members" '{"user_id": "eng-user-1", "role": "admin"}' || true
        admin_post "/api/v1/teams/${ENG_ID}/members" '{"user_id": "eng-user-2", "role": "member"}' || true
        admin_post "/api/v1/teams/${ENG_ID}/members" '{"user_id": "eng-user-3", "role": "member"}' || true
    fi
    if [ -n "$DS_ID" ]; then
        admin_post "/api/v1/teams/${DS_ID}/members" '{"user_id": "ds-user-1", "role": "admin"}' || true
        admin_post "/api/v1/teams/${DS_ID}/members" '{"user_id": "ds-user-2", "role": "member"}' || true
    fi
    if [ -n "$PROD_ID" ]; then
        admin_post "/api/v1/teams/${PROD_ID}/members" '{"user_id": "pm-user-1", "role": "admin"}' || true
        admin_post "/api/v1/teams/${PROD_ID}/members" '{"user_id": "pm-user-2", "role": "member"}' || true
    fi

    # =========================================================================
    # 3. Budgets (via Admin API)
    # =========================================================================
    echo ""
    echo "=== Seeding Budgets ==="

    admin_post "/api/v1/budgets" '{
        "name": "Global Monthly",
        "entity_type": "global",
        "monthly_limit": 5000.0,
        "soft_limit_percent": 0.8,
        "hard_limit_percent": 0.95,
        "alert_email": "platform-admin@example.com"
    }' || true

    admin_post "/api/v1/budgets" '{
        "name": "Engineering Budget",
        "entity_type": "team",
        "entity_id": "engineering",
        "monthly_limit": 500.0,
        "soft_limit_percent": 0.75,
        "hard_limit_percent": 1.0,
        "alert_email": "eng-lead@example.com"
    }' || true

    admin_post "/api/v1/budgets" '{
        "name": "Data Science Budget",
        "entity_type": "team",
        "entity_id": "data-science",
        "monthly_limit": 1000.0,
        "soft_limit_percent": 0.8,
        "hard_limit_percent": 1.0,
        "alert_email": "ds-lead@example.com"
    }' || true

    admin_post "/api/v1/budgets" '{
        "name": "Product Budget",
        "entity_type": "team",
        "entity_id": "product",
        "monthly_limit": 250.0,
        "soft_limit_percent": 0.85,
        "hard_limit_percent": 1.0,
        "alert_email": "pm-lead@example.com"
    }' || true

    admin_post "/api/v1/budgets" '{
        "name": "DevOps Budget",
        "entity_type": "team",
        "entity_id": "devops",
        "monthly_limit": 150.0,
        "soft_limit_percent": 0.9,
        "hard_limit_percent": 1.0,
        "alert_email": "devops-lead@example.com"
    }' || true

    admin_post "/api/v1/budgets" '{
        "name": "eng-user-1 Personal",
        "entity_type": "user",
        "entity_id": "eng-user-1",
        "monthly_limit": 100.0,
        "soft_limit_percent": 0.8,
        "hard_limit_percent": 1.0
    }' || true

    # =========================================================================
    # 4. MCP Servers (via Admin API)
    # =========================================================================
    echo ""
    echo "=== Seeding MCP Servers ==="

    admin_post "/api/v1/mcp-servers" '{
        "name": "Filesystem",
        "server_type": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"],
        "env": {}
    }' || true

    admin_post "/api/v1/mcp-servers" '{
        "name": "GitHub",
        "server_type": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {"GITHUB_TOKEN": "ghp_demo_token_placeholder"}
    }' || true

    admin_post "/api/v1/mcp-servers" '{
        "name": "PostgreSQL",
        "server_type": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-postgres", "postgresql://localhost:5432/mydb"],
        "env": {}
    }' || true

    admin_post "/api/v1/mcp-servers" '{
        "name": "Brave Search",
        "server_type": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-brave-search"],
        "env": {"BRAVE_API_KEY": "demo_brave_key_placeholder"}
    }' || true

    admin_post "/api/v1/mcp-servers" '{
        "name": "Internal Tools API",
        "server_type": "http",
        "url": "http://internal-tools:3001/mcp",
        "args": [],
        "env": {}
    }' || true

    admin_post "/api/v1/mcp-servers" '{
        "name": "Slack",
        "server_type": "stdio",
        "command": "npx",
        "args": ["-y", "@anthropic/mcp-server-slack"],
        "env": {"SLACK_BOT_TOKEN": "xoxb-demo-placeholder", "SLACK_TEAM_ID": "T0000000000"}
    }' || true

    # =========================================================================
    # 5. Workflows (via Admin API)
    # =========================================================================
    echo ""
    echo "=== Seeding Workflows ==="

    admin_post "/api/v1/workflows" '{
        "name": "Weekly Market Research",
        "template_type": "research",
        "description": "Automated weekly research report on AI industry trends and competitor analysis"
    }' || true

    admin_post "/api/v1/workflows" '{
        "name": "Code Review Pipeline",
        "template_type": "coding",
        "description": "Automated PR code review with security scanning and best-practice suggestions"
    }' || true

    admin_post "/api/v1/workflows" '{
        "name": "Customer Churn Analysis",
        "template_type": "data_analysis",
        "description": "Monthly analysis of customer churn patterns with predictive modeling"
    }' || true

    admin_post "/api/v1/workflows" '{
        "name": "Incident Postmortem Generator",
        "template_type": "research",
        "description": "Generate structured postmortem documents from incident timelines and logs"
    }' || true

    # =========================================================================
    # 6. Routing Policies (via Admin API)
    # =========================================================================
    echo ""
    echo "=== Seeding Routing Policies ==="

    admin_post "/api/v1/routing-policies" '{
        "name": "Cost-optimize free tier",
        "description": "Route free-tier users to budget-friendly models",
        "priority": 10,
        "condition": "user.tier == free",
        "action": "permit",
        "target_models": ["gpt-4o-mini", "claude-haiku-4.5"]
    }' || true

    admin_post "/api/v1/routing-policies" '{
        "name": "Premium model access",
        "description": "Allow premium users access to all models including GPT-4o and Claude Opus",
        "priority": 20,
        "condition": "user.tier == premium",
        "action": "permit",
        "target_models": ["gpt-4o", "claude-sonnet-4-5-20250929", "claude-opus-4-6", "gpt-4o-mini"]
    }' || true

    admin_post "/api/v1/routing-policies" '{
        "name": "Rate limit high-cost models",
        "description": "Restrict Opus usage when team budget exceeds 80%",
        "priority": 30,
        "condition": "team.budget_used_pct > 0.8",
        "action": "forbid",
        "target_models": ["claude-opus-4-6", "gpt-4o"]
    }' || true

fi

# =========================================================================
# 7. LLM Requests (generate real spend data)
# =========================================================================
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

# DevOps team requests
echo "DevOps team:"
make_request "gpt-4o-mini" "Write a Dockerfile for a Python FastAPI app." "devops-user-1" "devops" || true
make_request "gpt-4o-mini" "Explain blue-green deployment in 3 sentences." "devops-user-1" "devops" || true

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
echo "=== Demo data seeded! ==="
echo "  - API keys: 5 (team-scoped with budgets)"
echo "  - Teams: 5 (engineering, data-science, product, devops, security)"
echo "  - Budgets: 6 (1 global + 4 team + 1 user)"
echo "  - MCP servers: 6 (filesystem, github, postgres, brave, internal, slack)"
echo "  - Workflows: 4 (research, coding, data-analysis based)"
echo "  - Routing policies: 3 (tier-based routing + budget enforcement)"
echo "  - LLM requests: ~12 (across multiple models and teams)"
