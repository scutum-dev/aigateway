#!/bin/bash
#
# AI Gateway Interactive Demo Script
#
# Usage: ./scripts/demo.sh [scenario]
#
# Scenarios:
#   all           - Run all demos (default)
#   status        - Check service health
#   chat          - Interactive AI chat
#   cost          - Cost prediction
#   routing       - Routing policies (Admin API)
#   cache         - Semantic cache via LiteLLM
#   workflow      - Workflow engine
#   orgs          - Organizations & business units
#   guardrails    - Guardrails & DLP
#   prompts       - Prompt registry
#   ratelimits    - Rate limit policies
#   access        - Model access tiers
#   chargeback    - Cost allocation & chargeback
#   sla           - SLA monitoring & failover
#   abtests       - A/B testing
#   events        - Event subscriptions
#   audit         - Audit trail
#   mcp           - MCP server management
#   a2a           - A2A agent management
#   deprecation   - Model deprecation notices
#   vault         - Vault secrets management
#   observability - Observability stack URLs
#   e2e           - End-to-end flow
#   ui            - Admin dashboard
#

# Don't exit on error - handle errors gracefully in demos
# set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# Config
LITELLM_KEY="${LITELLM_KEY:-$LITELLM_KEY}"
VAULT_TOKEN="${VAULT_TOKEN:-root-token-for-dev}"
ADMIN_API="http://localhost:8086"
LITELLM_API="http://localhost:4000"
COST_PREDICTOR_API="http://localhost:8080"
WORKFLOW_API="http://localhost:8085"

# JWT token (populated by admin_login)
JWT_TOKEN=""

# ─────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────

print_header() {
    echo ""
    echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${WHITE}  $1${NC}"
    echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_step() {
    echo -e "${CYAN}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

print_command() {
    echo -e "${WHITE}$ $1${NC}"
}

wait_for_enter() {
    echo ""
    echo -e "${YELLOW}Press Enter to continue...${NC}"
    read -r
}

prompt_input() {
    local prompt="$1"
    local default="$2"
    local var_name="$3"

    if [ -n "$default" ]; then
        echo -ne "${CYAN}$prompt ${WHITE}[$default]${NC}: "
    else
        echo -ne "${CYAN}$prompt${NC}: "
    fi
    read -r input || true

    if [ -z "$input" ] && [ -n "$default" ]; then
        eval "$var_name='$default'"
    else
        eval "$var_name='$input'"
    fi
}

select_from_list() {
    local prompt="$1"
    shift
    local options=("$@")

    echo -e "${CYAN}$prompt${NC}"
    echo ""

    local i=1
    for opt in "${options[@]}"; do
        echo -e "  ${WHITE}$i)${NC} $opt"
        ((i++))
    done
    echo ""

    while true; do
        echo -ne "${CYAN}Select (1-${#options[@]})${NC}: "
        read -r choice || true

        if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#options[@]}" ]; then
            SELECTED="${options[$((choice-1))]}"
            return 0
        fi
        echo -e "${RED}Invalid choice. Please try again.${NC}"
    done
}

check_service() {
    local url="$1"
    local name="$2"

    if curl -s -o /dev/null -w "%{http_code}" --max-time 3 "$url" | grep -q "200\|204\|406"; then
        echo -e "  ${GREEN}✓${NC} $name"
        return 0
    else
        echo -e "  ${RED}✗${NC} $name"
        return 1
    fi
}

# Authenticate with Admin API and set JWT_TOKEN
admin_login() {
    if [ -n "$JWT_TOKEN" ]; then
        return 0
    fi

    print_step "Authenticating with Admin API..."
    local login_response
    login_response=$(curl -s "${ADMIN_API}/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"api_key\": \"${LITELLM_KEY}\"}")

    JWT_TOKEN=$(echo "$login_response" | jq -r '.access_token // empty')

    if [ -z "$JWT_TOKEN" ]; then
        print_error "Failed to authenticate with Admin API"
        echo "$login_response" | jq . 2>/dev/null || echo "$login_response"
        return 1
    fi

    print_success "Authenticated successfully"
    echo ""
}

# Helper: make authenticated Admin API requests
admin_get() {
    curl -s "${ADMIN_API}$1" -H "Authorization: Bearer ${JWT_TOKEN}"
}

admin_post() {
    curl -s "${ADMIN_API}$1" \
        -H "Authorization: Bearer ${JWT_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "$2"
}

admin_put() {
    curl -s -X PUT "${ADMIN_API}$1" \
        -H "Authorization: Bearer ${JWT_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "$2"
}

# Fetch real data functions
fetch_models() {
    curl -s ${LITELLM_API}/v1/models \
        -H "Authorization: Bearer $LITELLM_KEY" | jq -r '.data[].id' 2>/dev/null
}

fetch_workflow_templates() {
    curl -s ${WORKFLOW_API}/api/v1/templates | jq -r '.templates[].type // .[] | if type == "object" then .type else . end' 2>/dev/null
}

# ─────────────────────────────────────────────
# Demo: Platform Status
# ─────────────────────────────────────────────

demo_status() {
    print_header "Platform Status Check"

    print_step "Checking service health..."
    echo ""

    local healthy=0
    local total=0

    services=(
        "http://localhost:4000/health/liveliness|LiteLLM (AI Proxy)"
        "http://localhost:8086/health|Admin API"
        "http://localhost:8085/health|Workflow Engine"
        "http://localhost:8080/health|Cost Predictor"
        "http://localhost:8081/health|Budget Webhook"
        "http://localhost:5173|Admin UI"
        "http://localhost:8087/health|A2A Runtime"
        "http://localhost:8088|Temporal UI"
        "http://localhost:9090/-/healthy|Prometheus"
        "http://localhost:3030/api/health|Grafana"
        "http://localhost:8200/v1/sys/health|Vault"
        "http://localhost:9000/|Agent Gateway"
    )

    for service in "${services[@]}"; do
        url="${service%%|*}"
        name="${service##*|}"
        total=$((total + 1))
        if check_service "$url" "$name"; then
            healthy=$((healthy + 1))
        fi
    done

    echo ""
    if [ "$healthy" -eq "$total" ]; then
        print_success "All $total services healthy!"
    else
        print_warning "$healthy/$total services healthy"
    fi
}

# ─────────────────────────────────────────────
# Demo: AI Chat
# ─────────────────────────────────────────────

demo_chat() {
    print_header "Demo: AI Chat Completion"

    print_info "Interactive chat with multiple AI providers"
    echo ""

    # Fetch and display available models
    print_step "Fetching available models..."
    echo ""

    models_list=$(fetch_models)
    if [ -z "$models_list" ]; then
        print_error "Could not fetch models. Is LiteLLM running?"
        return 1
    fi

    # Convert to array
    IFS=$'\n' read -r -d '' -a models_array <<< "$models_list" || true

    echo -e "${WHITE}Available models:${NC}"
    local i=1
    for model in "${models_array[@]}"; do
        echo -e "  ${WHITE}$i)${NC} $model"
        ((i++))
    done
    echo ""

    # Let user select model
    while true; do
        echo -ne "${CYAN}Select model (1-${#models_array[@]})${NC}: "
        read -r choice || true

        if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#models_array[@]}" ]; then
            selected_model="${models_array[$((choice-1))]}"
            break
        fi
        echo -e "${RED}Invalid choice. Please try again.${NC}"
    done

    echo ""
    print_success "Selected: $selected_model"
    echo ""

    # Get user's message
    echo -ne "${CYAN}Enter your message${NC}: "
    read -r user_message || true

    if [ -z "$user_message" ]; then
        user_message="Hello, introduce yourself briefly."
    fi

    echo ""
    print_step "Sending chat completion request..."
    echo ""

    # Make the request
    response=$(curl -s ${LITELLM_API}/v1/chat/completions \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $LITELLM_KEY" \
        -d "{
            \"model\": \"$selected_model\",
            \"messages\": [{\"role\": \"user\", \"content\": \"$user_message\"}],
            \"max_tokens\": 500
        }")

    content=$(echo "$response" | jq -r '.choices[0].message.content' 2>/dev/null)

    if [ -n "$content" ] && [ "$content" != "null" ]; then
        echo -e "${WHITE}Response from $selected_model:${NC}"
        echo -e "${GREEN}$content${NC}"
        echo ""

        # Show usage stats
        prompt_tokens=$(echo "$response" | jq -r '.usage.prompt_tokens' 2>/dev/null)
        completion_tokens=$(echo "$response" | jq -r '.usage.completion_tokens' 2>/dev/null)
        total_tokens=$(echo "$response" | jq -r '.usage.total_tokens' 2>/dev/null)

        echo -e "${BLUE}Token usage:${NC}"
        echo -e "  Prompt: $prompt_tokens | Completion: $completion_tokens | Total: $total_tokens"

        print_success "Chat completion successful"
    else
        print_error "Chat completion failed"
        echo "$response" | jq . 2>/dev/null || echo "$response"
    fi

    # Ask if user wants to continue chatting
    echo ""
    echo -ne "${CYAN}Continue chatting? (y/n)${NC}: "
    read -r continue_chat || true

    if [[ "$continue_chat" =~ ^[Yy] ]]; then
        demo_chat
    fi
}

# ─────────────────────────────────────────────
# Demo: Cost Prediction
# ─────────────────────────────────────────────

demo_cost() {
    print_header "Demo: Cost Prediction"

    print_info "Predict request costs before execution"
    echo ""

    # Fetch models for selection
    print_step "Fetching available models..."
    models_list=$(fetch_models)
    IFS=$'\n' read -r -d '' -a models_array <<< "$models_list" || true

    echo ""
    echo -e "${WHITE}Select model to estimate cost:${NC}"
    local i=1
    for model in "${models_array[@]}"; do
        echo -e "  ${WHITE}$i)${NC} $model"
        ((i++))
    done
    echo ""

    while true; do
        echo -ne "${CYAN}Select model (1-${#models_array[@]})${NC}: "
        read -r choice || true

        if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#models_array[@]}" ]; then
            selected_model="${models_array[$((choice-1))]}"
            break
        fi
        echo -e "${RED}Invalid choice.${NC}"
    done

    echo ""
    echo -ne "${CYAN}Enter your prompt (or press Enter for sample)${NC}: "
    read -r user_prompt || true

    if [ -z "$user_prompt" ]; then
        user_prompt="Write a detailed analysis of AI trends in 2024"
    fi

    echo -ne "${CYAN}Max tokens to generate${NC} [1000]: "
    read -r max_tokens || true
    max_tokens=${max_tokens:-1000}

    echo ""
    print_step "Predicting cost for $selected_model..."
    echo ""

    prediction=$(curl -s ${COST_PREDICTOR_API}/predict \
        -H "Content-Type: application/json" \
        -d "{
            \"model\": \"$selected_model\",
            \"messages\": [{\"role\": \"user\", \"content\": \"$user_prompt\"}],
            \"max_tokens\": $max_tokens
        }")

    if echo "$prediction" | jq . >/dev/null 2>&1; then
        echo -e "${WHITE}Cost Prediction for $selected_model:${NC}"
        echo ""

        input_tokens=$(echo "$prediction" | jq -r '.input_tokens // "N/A"')
        estimated_output=$(echo "$prediction" | jq -r '.estimated_output_tokens // "N/A"')
        input_cost=$(echo "$prediction" | jq -r '.input_cost_usd // "N/A"')
        output_cost=$(echo "$prediction" | jq -r '.estimated_output_cost_usd // "N/A"')
        total_cost=$(echo "$prediction" | jq -r '.total_estimated_cost_usd // "N/A"')

        echo -e "  ${CYAN}Input tokens:${NC}     $input_tokens"
        echo -e "  ${CYAN}Est. output:${NC}      $estimated_output"
        echo -e "  ${CYAN}Input cost:${NC}       \$$input_cost"
        echo -e "  ${CYAN}Output cost:${NC}      \$$output_cost"
        echo -e "  ${GREEN}Total estimate:${NC}   \$$total_cost"

        print_success "Cost prediction complete"
    else
        print_warning "Cost predictor response: $prediction"
    fi

    # Compare with other models
    echo ""
    echo -ne "${CYAN}Compare with other models? (y/n)${NC}: "
    read -r compare || true

    if [[ "$compare" =~ ^[Yy] ]]; then
        echo ""
        print_step "Comparing costs across all models..."
        echo ""

        echo -e "${WHITE}Model                          Est. Cost${NC}"
        echo -e "─────────────────────────────────────────"

        for model in "${models_array[@]}"; do
            cost=$(curl -s ${COST_PREDICTOR_API}/predict \
                -H "Content-Type: application/json" \
                -d "{
                    \"model\": \"$model\",
                    \"messages\": [{\"role\": \"user\", \"content\": \"$user_prompt\"}],
                    \"max_tokens\": $max_tokens
                }" | jq -r '.total_estimated_cost_usd // "N/A"' 2>/dev/null)

            printf "  %-28s \$%s\n" "$model" "$cost"
        done
    fi
}

# ─────────────────────────────────────────────
# Demo: Routing Policies (Admin API)
# ─────────────────────────────────────────────

demo_routing() {
    print_header "Demo: Routing Policies"

    print_info "Create and manage model routing policies via Admin API"
    echo ""

    admin_login || return 1

    # List existing policies
    print_step "Listing current routing policies..."
    echo ""

    policies=$(admin_get "/api/v1/routing-policies")
    policy_count=$(echo "$policies" | jq 'length' 2>/dev/null)

    if [ -n "$policy_count" ] && [ "$policy_count" != "null" ]; then
        echo -e "${WHITE}Current policies: $policy_count${NC}"
        echo "$policies" | jq -r '.[] | "  \(.policy_type) | \(.name) | active=\(.is_active)"' 2>/dev/null
    else
        echo -e "  No policies found or could not parse response"
    fi

    echo ""

    # Create a new fallback policy
    print_step "Creating a new fallback routing policy..."
    echo ""

    create_result=$(admin_post "/api/v1/routing-policies" '{
        "name": "Demo Fallback Chain",
        "description": "Demo: GPT-4o with Claude and Gemini fallbacks",
        "policy_type": "fallback",
        "config": {
            "model": "gpt-4o",
            "fallbacks": ["claude-3-5-sonnet", "gemini-1.5-pro"]
        },
        "priority": 10,
        "is_active": true
    }')

    policy_id=$(echo "$create_result" | jq -r '.id // empty')

    if [ -n "$policy_id" ]; then
        echo -e "${WHITE}Created routing policy:${NC}"
        echo -e "  ${CYAN}ID:${NC}     $policy_id"
        echo -e "  ${CYAN}Type:${NC}   fallback"
        echo -e "  ${CYAN}Model:${NC}  gpt-4o -> [claude-3-5-sonnet, gemini-1.5-pro]"
        echo ""
        print_success "Policy created and synced to LiteLLM"
    else
        print_warning "Could not create policy (may already exist)"
        echo "$create_result" | jq -r '.detail // .' 2>/dev/null
    fi

    echo ""

    # Show LiteLLM sync status
    print_step "Checking LiteLLM router status..."
    echo ""

    sync_status=$(admin_get "/api/v1/routing-policies/litellm-status")
    echo "$sync_status" | jq '.' 2>/dev/null || echo "$sync_status"

    print_success "Routing policies demo complete"
}

# ─────────────────────────────────────────────
# Demo: Semantic Cache
# ─────────────────────────────────────────────

demo_cache() {
    print_header "Demo: Semantic Cache"

    print_info "LiteLLM-native caching with Admin API management"
    echo ""

    admin_login || return 1

    # Show current cache settings
    print_step "Fetching cache settings..."
    echo ""

    settings=$(admin_get "/api/v1/cache/settings")
    echo -e "${WHITE}Cache Configuration:${NC}"
    echo "$settings" | jq '.' 2>/dev/null || echo "$settings"
    echo ""

    # Fetch models
    print_step "Fetching available models..."
    models_list=$(fetch_models)
    IFS=$'\n' read -r -d '' -a models_array <<< "$models_list" || true

    echo ""
    echo -e "${WHITE}Select model for cache test:${NC}"
    local i=1
    for model in "${models_array[@]}"; do
        echo -e "  ${WHITE}$i)${NC} $model"
        ((i++))
    done
    echo ""

    while true; do
        echo -ne "${CYAN}Select model (1-${#models_array[@]})${NC}: "
        read -r choice || true

        if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#models_array[@]}" ]; then
            selected_model="${models_array[$((choice-1))]}"
            break
        fi
        echo -e "${RED}Invalid choice.${NC}"
    done

    echo ""
    echo -ne "${CYAN}Enter a query${NC} [What is machine learning?]: "
    read -r original_query || true
    original_query=${original_query:-"What is machine learning?"}

    echo ""
    print_step "First request (should be a fresh call)..."
    echo ""

    start1=$(date +%s%N 2>/dev/null || python3 -c 'import time; print(int(time.time()*1e9))')

    response1=$(curl -s ${LITELLM_API}/v1/chat/completions \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $LITELLM_KEY" \
        -d "{
            \"model\": \"$selected_model\",
            \"messages\": [{\"role\": \"user\", \"content\": \"$original_query\"}],
            \"max_tokens\": 200
        }")

    end1=$(date +%s%N 2>/dev/null || python3 -c 'import time; print(int(time.time()*1e9))')
    duration1=$(( (end1 - start1) / 1000000 ))

    content1=$(echo "$response1" | jq -r '.choices[0].message.content // empty')

    if [ -n "$content1" ] && [ "$content1" != "null" ]; then
        echo -e "${WHITE}Response (${duration1}ms):${NC}"
        echo -e "${GREEN}${content1:0:300}${NC}"
        [ ${#content1} -gt 300 ] && echo -e "${GREEN}...${NC}"
    else
        print_error "First request failed"
        echo "$response1" | jq . 2>/dev/null || echo "$response1"
        return 1
    fi

    echo ""
    print_step "Second request with same prompt (may hit cache)..."
    echo ""

    start2=$(date +%s%N 2>/dev/null || python3 -c 'import time; print(int(time.time()*1e9))')

    response2=$(curl -s ${LITELLM_API}/v1/chat/completions \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $LITELLM_KEY" \
        -d "{
            \"model\": \"$selected_model\",
            \"messages\": [{\"role\": \"user\", \"content\": \"$original_query\"}],
            \"max_tokens\": 200
        }")

    end2=$(date +%s%N 2>/dev/null || python3 -c 'import time; print(int(time.time()*1e9))')
    duration2=$(( (end2 - start2) / 1000000 ))

    content2=$(echo "$response2" | jq -r '.choices[0].message.content // empty')

    echo -e "${WHITE}Response (${duration2}ms):${NC}"
    echo -e "${GREEN}${content2:0:300}${NC}"
    [ ${#content2} -gt 300 ] && echo -e "${GREEN}...${NC}"

    echo ""
    echo -e "${WHITE}Timing comparison:${NC}"
    echo -e "  ${CYAN}First request:${NC}   ${duration1}ms"
    echo -e "  ${CYAN}Second request:${NC}  ${duration2}ms"
    if [ "$duration2" -lt "$duration1" ]; then
        speedup=$(( duration1 - duration2 ))
        echo -e "  ${GREEN}Faster by:${NC}       ${speedup}ms"
    fi

    echo ""

    # Show cache stats
    print_step "Cache statistics..."
    echo ""

    stats=$(admin_get "/api/v1/cache/stats")
    echo -e "${WHITE}Cache Stats:${NC}"
    echo "$stats" | jq '.' 2>/dev/null || echo "$stats"

    print_success "Semantic cache demo complete"
}

# ─────────────────────────────────────────────
# Demo: Workflow Engine
# ─────────────────────────────────────────────

demo_workflow() {
    print_header "Demo: Workflow Engine"

    print_info "LangGraph-powered multi-step AI workflows"
    echo ""

    # Fetch available templates
    print_step "Fetching workflow templates..."
    echo ""

    templates_response=$(curl -s ${WORKFLOW_API}/api/v1/templates)

    # Parse templates - handle different response formats
    templates=$(echo "$templates_response" | jq -r '.templates[] | "\(.type)|\(.name)|\(.description)"' 2>/dev/null)

    if [ -z "$templates" ]; then
        templates=$(echo "$templates_response" | jq -r '.[] | "\(.type)|\(.name)|\(.description)"' 2>/dev/null)
    fi

    if [ -z "$templates" ]; then
        print_error "Could not fetch templates"
        echo "$templates_response" | jq . 2>/dev/null
        return 1
    fi

    echo -e "${WHITE}Available Workflow Templates:${NC}"
    echo ""

    IFS=$'\n' read -r -d '' -a templates_array <<< "$templates" || true
    local i=1
    for template in "${templates_array[@]}"; do
        type=$(echo "$template" | cut -d'|' -f1)
        name=$(echo "$template" | cut -d'|' -f2)
        desc=$(echo "$template" | cut -d'|' -f3)
        echo -e "  ${WHITE}$i)${NC} ${GREEN}$name${NC} ($type)"
        echo -e "     ${BLUE}$desc${NC}"
        echo ""
        ((i++))
    done

    # Select template
    while true; do
        echo -ne "${CYAN}Select template (1-${#templates_array[@]})${NC}: "
        read -r choice || true

        if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#templates_array[@]}" ]; then
            selected_template=$(echo "${templates_array[$((choice-1))]}" | cut -d'|' -f1)
            break
        fi
        echo -e "${RED}Invalid choice.${NC}"
    done

    echo ""

    # Get input based on template type
    case "$selected_template" in
        research)
            echo -ne "${CYAN}Enter research query${NC}: "
            read -r query || true
            input_json="{\"query\": \"$query\"}"
            ;;
        coding)
            echo -ne "${CYAN}Enter coding task${NC}: "
            read -r task || true
            echo -ne "${CYAN}Programming language${NC} [python]: "
            read -r language || true
            language=${language:-python}
            input_json="{\"task\": \"$task\", \"language\": \"$language\"}"
            ;;
        data_analysis)
            echo -ne "${CYAN}Enter analysis question${NC}: "
            read -r question || true
            input_json="{\"question\": \"$question\"}"
            ;;
        *)
            echo -ne "${CYAN}Enter input (JSON or plain text)${NC}: "
            read -r user_input || true
            if echo "$user_input" | jq . >/dev/null 2>&1; then
                input_json="$user_input"
            else
                input_json="{\"input\": \"$user_input\"}"
            fi
            ;;
    esac

    echo ""
    print_step "Starting $selected_template workflow..."
    echo ""

    execution=$(curl -s ${WORKFLOW_API}/api/v1/executions \
        -H "Content-Type: application/json" \
        -d "{
            \"template\": \"$selected_template\",
            \"input\": $input_json
        }")

    exec_id=$(echo "$execution" | jq -r '.execution_id // .id // empty')
    status=$(echo "$execution" | jq -r '.status // "unknown"')
    error=$(echo "$execution" | jq -r '.error // empty')

    if [ -n "$exec_id" ]; then
        echo -e "${WHITE}Execution Started:${NC}"
        echo -e "  ${CYAN}ID:${NC}     $exec_id"
        echo -e "  ${CYAN}Status:${NC} $status"

        if [ -n "$error" ] && [ "$error" != "null" ]; then
            echo -e "  ${RED}Error:${NC}  $error"
        fi

        if [ "$status" = "completed" ]; then
            output=$(echo "$execution" | jq -r '.output // empty')
            if [ -n "$output" ] && [ "$output" != "null" ]; then
                echo ""
                echo -e "${WHITE}Output:${NC}"
                echo "$output" | jq . 2>/dev/null || echo "$output"
            fi

            cost=$(echo "$execution" | jq -r '.total_cost // "N/A"')
            tokens=$(echo "$execution" | jq -r '.total_tokens // "N/A"')
            echo ""
            echo -e "  ${CYAN}Total Cost:${NC}   \$$cost"
            echo -e "  ${CYAN}Total Tokens:${NC} $tokens"
        fi

        print_success "Workflow execution complete"
    else
        print_error "Failed to start workflow"
        echo "$execution" | jq . 2>/dev/null || echo "$execution"
    fi
}

# ─────────────────────────────────────────────
# Demo: Organizations
# ─────────────────────────────────────────────

demo_orgs() {
    print_header "Demo: Organizations & Business Units"

    print_info "Multi-tenant organization hierarchy: Org -> BU -> Team -> Member"
    echo ""

    admin_login || return 1

    # List existing orgs
    print_step "Listing existing organizations..."
    echo ""

    orgs=$(admin_get "/api/v1/organizations")
    echo "$orgs" | jq -r '.[] | "  \(.name) (\(.slug)) - \(.team_count // 0) teams, \(.member_count // 0) members"' 2>/dev/null || echo "  No organizations found"
    echo ""

    # Create a new org
    print_step "Creating a new organization..."
    echo ""

    org_result=$(admin_post "/api/v1/organizations" '{
        "name": "Demo Corporation",
        "slug": "demo-corp",
        "description": "Demo organization for showcasing multi-tenancy",
        "max_budget": 10000.00,
        "allowed_models": ["gpt-4o", "gpt-4o-mini", "claude-3-5-sonnet"]
    }')

    org_id=$(echo "$org_result" | jq -r '.id // empty')

    if [ -n "$org_id" ]; then
        echo -e "${WHITE}Organization created:${NC}"
        echo -e "  ${CYAN}ID:${NC}     $org_id"
        echo -e "  ${CYAN}Name:${NC}   Demo Corporation"
        echo -e "  ${CYAN}Slug:${NC}   demo-corp"
        echo -e "  ${CYAN}Budget:${NC} \$10,000"
        echo ""
        print_success "Organization created"

        # Create a business unit
        echo ""
        print_step "Creating a business unit..."
        echo ""

        bu_result=$(admin_post "/api/v1/organizations/${org_id}/business-units" '{
            "name": "Engineering",
            "description": "Product engineering department",
            "cost_center": "CC-4200"
        }')

        bu_id=$(echo "$bu_result" | jq -r '.id // empty')

        if [ -n "$bu_id" ]; then
            echo -e "  ${CYAN}BU ID:${NC}       $bu_id"
            echo -e "  ${CYAN}BU Name:${NC}     Engineering"
            echo -e "  ${CYAN}Cost Center:${NC} CC-4200"
            print_success "Business unit created"
        else
            print_warning "Could not create business unit"
            echo "$bu_result" | jq -r '.detail // .' 2>/dev/null
        fi

        # Add a member
        echo ""
        print_step "Adding a member to the organization..."
        echo ""

        member_result=$(admin_post "/api/v1/organizations/${org_id}/members" '{
            "user_id": "demo-user",
            "role": "admin"
        }')

        if echo "$member_result" | jq -r '.user_id // empty' | grep -q "demo-user"; then
            echo -e "  ${CYAN}User:${NC} demo-user"
            echo -e "  ${CYAN}Role:${NC} admin"
            print_success "Member added"
        else
            print_warning "Could not add member"
            echo "$member_result" | jq -r '.detail // .' 2>/dev/null
        fi
    else
        print_warning "Could not create organization (may already exist)"
        echo "$org_result" | jq -r '.detail // .' 2>/dev/null
    fi

    print_success "Organizations demo complete"
}

# ─────────────────────────────────────────────
# Demo: Guardrails & DLP
# ─────────────────────────────────────────────

demo_guardrails() {
    print_header "Demo: Guardrails & DLP"

    print_info "Content safety, PII detection, and data loss prevention"
    echo ""

    admin_login || return 1

    # Create a guardrail config
    print_step "Creating a guardrail configuration..."
    echo ""

    guardrail_result=$(admin_post "/api/v1/guardrails" '{
        "name": "Demo Safety Profile",
        "description": "Demo guardrail with PII detection and toxicity filtering",
        "enable_pii_detection": true,
        "pii_action": "anonymize",
        "pii_entities": ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD"],
        "enable_toxicity": true,
        "toxicity_threshold": 0.70,
        "enable_secrets_detection": true,
        "mode": "block",
        "on_fail": "block",
        "is_active": true
    }')

    guardrail_id=$(echo "$guardrail_result" | jq -r '.id // empty')

    if [ -n "$guardrail_id" ]; then
        echo -e "${WHITE}Guardrail created:${NC}"
        echo -e "  ${CYAN}ID:${NC}         $guardrail_id"
        echo -e "  ${CYAN}PII:${NC}        enabled (anonymize)"
        echo -e "  ${CYAN}Toxicity:${NC}   enabled (threshold: 0.70)"
        echo -e "  ${CYAN}Secrets:${NC}    enabled"
        echo -e "  ${CYAN}Mode:${NC}       block"
        print_success "Guardrail created"
    else
        print_warning "Could not create guardrail"
        echo "$guardrail_result" | jq -r '.detail // .' 2>/dev/null
    fi

    echo ""

    # Create a DLP detector
    print_step "Creating a DLP content detector..."
    echo ""

    detector_result=$(admin_post "/api/v1/detectors" '{
        "name": "Demo AWS Key Detector",
        "description": "Detects AWS access key IDs in prompts",
        "detector_type": "regex",
        "config": {
            "patterns": [
                {
                    "pattern": "AKIA[0-9A-Z]{16}",
                    "label": "aws_access_key",
                    "action": "block"
                }
            ]
        }
    }')

    detector_id=$(echo "$detector_result" | jq -r '.id // empty')

    if [ -n "$detector_id" ]; then
        echo -e "${WHITE}DLP Detector created:${NC}"
        echo -e "  ${CYAN}ID:${NC}      $detector_id"
        echo -e "  ${CYAN}Type:${NC}    regex"
        echo -e "  ${CYAN}Pattern:${NC} AKIA[0-9A-Z]{16}"
        print_success "Detector created"
    else
        print_warning "Could not create detector"
        echo "$detector_result" | jq -r '.detail // .' 2>/dev/null
    fi

    echo ""

    # Scan text for sensitive content
    print_step "Scanning sample text for sensitive content..."
    echo ""

    scan_result=$(admin_post "/api/v1/scan" '{
        "text": "My AWS key is AKIAIOSFODNN7EXAMPLE and my email is john@example.com. Please help me deploy.",
        "detectors": ["all"]
    }')

    echo -e "${WHITE}Scan Results:${NC}"
    echo "$scan_result" | jq '.' 2>/dev/null || echo "$scan_result"

    print_success "Guardrails & DLP demo complete"
}

# ─────────────────────────────────────────────
# Demo: Prompt Registry
# ─────────────────────────────────────────────

demo_prompts() {
    print_header "Demo: Prompt Registry"

    print_info "Versioned prompt templates with rendering and approval workflow"
    echo ""

    admin_login || return 1

    # List existing prompts
    print_step "Listing prompt templates..."
    echo ""

    prompts=$(admin_get "/api/v1/prompts")
    prompt_count=$(echo "$prompts" | jq 'length' 2>/dev/null)
    echo -e "  Found ${prompt_count:-0} existing prompt templates"
    echo ""

    # Create a prompt template
    print_step "Creating a new prompt template..."
    echo ""

    prompt_result=$(admin_post "/api/v1/prompts" '{
        "name": "Demo Code Reviewer",
        "slug": "demo-code-review",
        "description": "Reviews code and provides feedback",
        "category": "engineering",
        "template_text": "Review the following {{language}} code and provide feedback on quality, bugs, and improvements:\n\n```{{language}}\n{{code}}\n```",
        "variables": [
            {"name": "language", "type": "string", "required": true, "default": "python"},
            {"name": "code", "type": "string", "required": true}
        ],
        "model_hint": "gpt-4o",
        "tags": ["engineering", "code-review"]
    }')

    prompt_id=$(echo "$prompt_result" | jq -r '.id // empty')

    if [ -n "$prompt_id" ]; then
        echo -e "${WHITE}Prompt template created:${NC}"
        echo -e "  ${CYAN}ID:${NC}       $prompt_id"
        echo -e "  ${CYAN}Slug:${NC}     demo-code-review"
        echo -e "  ${CYAN}Vars:${NC}     language, code"
        echo -e "  ${CYAN}Model:${NC}    gpt-4o"
        print_success "Template created"
    else
        print_warning "Could not create template (slug may already exist)"
        echo "$prompt_result" | jq -r '.detail // .' 2>/dev/null
    fi

    echo ""

    # Render the template
    print_step "Rendering template with variables..."
    echo ""

    render_result=$(admin_post "/api/v1/prompts/demo-code-review/render" '{
        "variables": {
            "language": "python",
            "code": "def add(a, b): return a + b"
        }
    }')

    rendered=$(echo "$render_result" | jq -r '.rendered_text // .rendered // empty')

    if [ -n "$rendered" ]; then
        echo -e "${WHITE}Rendered prompt:${NC}"
        echo -e "${GREEN}$rendered${NC}"
        print_success "Template rendered"
    else
        echo "$render_result" | jq '.' 2>/dev/null || echo "$render_result"
    fi

    echo ""

    # Submit for review
    if [ -n "$prompt_id" ]; then
        print_step "Submitting template for review..."
        echo ""

        review_result=$(admin_post "/api/v1/prompts/${prompt_id}/submit-review" '{}')
        echo "$review_result" | jq -r '"  Status: \(.status // "submitted")"' 2>/dev/null
        print_success "Submitted for approval"
    fi

    print_success "Prompt registry demo complete"
}

# ─────────────────────────────────────────────
# Demo: Rate Limits
# ─────────────────────────────────────────────

demo_ratelimits() {
    print_header "Demo: Rate Limit Policies"

    print_info "Per-team, per-user, and per-model rate limiting"
    echo ""

    admin_login || return 1

    # List existing rate limits
    print_step "Listing existing rate limit policies..."
    echo ""

    limits=$(admin_get "/api/v1/rate-limits")
    echo "$limits" | jq -r '.[] | "  \(.name) | scope=\(.scope) | rpm=\(.rpm_limit) tpm=\(.tpm_limit)"' 2>/dev/null || echo "  No policies found"
    echo ""

    # Create a rate limit policy
    print_step "Creating a rate limit policy..."
    echo ""

    limit_result=$(admin_post "/api/v1/rate-limits" '{
        "name": "Demo Team Rate Limit",
        "description": "Rate limits for demo team",
        "scope": "team",
        "scope_value": "demo-team",
        "rpm_limit": 60,
        "tpm_limit": 100000,
        "rpd_limit": 5000,
        "burst_multiplier": 1.5,
        "burst_window_seconds": 10,
        "priority": 0
    }')

    limit_id=$(echo "$limit_result" | jq -r '.id // empty')

    if [ -n "$limit_id" ]; then
        echo -e "${WHITE}Rate limit policy created:${NC}"
        echo -e "  ${CYAN}ID:${NC}    $limit_id"
        echo -e "  ${CYAN}Scope:${NC} team (demo-team)"
        echo -e "  ${CYAN}RPM:${NC}   60"
        echo -e "  ${CYAN}TPM:${NC}   100,000"
        echo -e "  ${CYAN}RPD:${NC}   5,000"
        echo -e "  ${CYAN}Burst:${NC} 1.5x for 10s"
        print_success "Policy created"
    else
        print_warning "Could not create policy"
        echo "$limit_result" | jq -r '.detail // .' 2>/dev/null
    fi

    echo ""

    # Pre-flight check
    print_step "Running pre-flight rate limit check..."
    echo ""

    check_result=$(admin_post "/api/v1/rate-limits/check" '{
        "scope": "team",
        "scope_value": "demo-team",
        "model": "gpt-4o",
        "estimated_tokens": 500
    }')

    echo -e "${WHITE}Pre-flight Check:${NC}"
    echo "$check_result" | jq '.' 2>/dev/null || echo "$check_result"

    print_success "Rate limits demo complete"
}

# ─────────────────────────────────────────────
# Demo: Model Access
# ─────────────────────────────────────────────

demo_access() {
    print_header "Demo: Model Access Tiers"

    print_info "Tiered model access with approval workflows"
    echo ""

    admin_login || return 1

    # List existing tiers
    print_step "Listing existing access tiers..."
    echo ""

    tiers=$(admin_get "/api/v1/model-access/tiers")
    echo "$tiers" | jq -r '.[] | "  \(.name) - \(.models | length) models, approval=\(.requires_approval)"' 2>/dev/null || echo "  No tiers found"
    echo ""

    # Create an access tier
    print_step "Creating a premium access tier..."
    echo ""

    tier_result=$(admin_post "/api/v1/model-access/tiers" '{
        "name": "Demo Premium Tier",
        "description": "Access tier for frontier models requiring approval",
        "requires_approval": true,
        "requires_justification": true,
        "max_grant_duration_days": 90,
        "models": ["gpt-4o", "claude-3-5-sonnet", "gemini-1.5-pro"]
    }')

    tier_id=$(echo "$tier_result" | jq -r '.id // empty')

    if [ -n "$tier_id" ]; then
        echo -e "${WHITE}Access tier created:${NC}"
        echo -e "  ${CYAN}ID:${NC}        $tier_id"
        echo -e "  ${CYAN}Models:${NC}    gpt-4o, claude-3-5-sonnet, gemini-1.5-pro"
        echo -e "  ${CYAN}Approval:${NC}  required"
        echo -e "  ${CYAN}Duration:${NC}  90 days max"
        print_success "Tier created"
    else
        print_warning "Could not create tier"
        echo "$tier_result" | jq -r '.detail // .' 2>/dev/null
    fi

    echo ""

    # Submit access request
    print_step "Submitting a model access request..."
    echo ""

    request_result=$(admin_post "/api/v1/model-access/requests" '{
        "tier_id": "'"${tier_id}"'",
        "justification": "Need frontier models for production code review pipeline"
    }')

    request_id=$(echo "$request_result" | jq -r '.id // empty')

    if [ -n "$request_id" ]; then
        echo -e "${WHITE}Access request submitted:${NC}"
        echo -e "  ${CYAN}Request ID:${NC}     $request_id"
        echo -e "  ${CYAN}Status:${NC}         pending"
        echo -e "  ${CYAN}Justification:${NC}  Need frontier models for production code review"
        print_success "Request submitted"

        # Approve it
        echo ""
        print_step "Approving the access request..."
        echo ""

        approve_result=$(admin_post "/api/v1/model-access/requests/${request_id}/approve" '{}')
        echo -e "  ${GREEN}Status: approved${NC}"
        print_success "Request approved"
    else
        print_warning "Could not submit request"
        echo "$request_result" | jq -r '.detail // .' 2>/dev/null
    fi

    print_success "Model access demo complete"
}

# ─────────────────────────────────────────────
# Demo: Chargeback
# ─────────────────────────────────────────────

demo_chargeback() {
    print_header "Demo: Cost Allocation & Chargeback"

    print_info "Allocate AI costs to departments and generate chargeback reports"
    echo ""

    admin_login || return 1

    # Create a cost allocation rule
    print_step "Creating a cost allocation rule..."
    echo ""

    rule_result=$(admin_post "/api/v1/cost-allocation/rules" '{
        "name": "Demo Engineering Allocation",
        "team_id": "demo-team",
        "allocation_type": "department",
        "allocation_target": "R&D",
        "allocation_percent": 75.0,
        "metadata": {
            "cost_center": "CC-4200",
            "gl_code": "7100"
        }
    }')

    rule_id=$(echo "$rule_result" | jq -r '.id // empty')

    if [ -n "$rule_id" ]; then
        echo -e "${WHITE}Allocation rule created:${NC}"
        echo -e "  ${CYAN}ID:${NC}           $rule_id"
        echo -e "  ${CYAN}Team:${NC}         demo-team"
        echo -e "  ${CYAN}Target:${NC}       R&D department"
        echo -e "  ${CYAN}Allocation:${NC}   75%"
        echo -e "  ${CYAN}Cost Center:${NC}  CC-4200"
        print_success "Rule created"
    else
        print_warning "Could not create rule"
        echo "$rule_result" | jq -r '.detail // .' 2>/dev/null
    fi

    echo ""

    # Generate a chargeback report
    print_step "Generating chargeback report..."
    echo ""

    report_result=$(admin_post "/api/v1/chargeback/reports/generate" '{
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "name": "Demo January Report"
    }')

    report_id=$(echo "$report_result" | jq -r '.id // empty')

    if [ -n "$report_id" ]; then
        echo -e "${WHITE}Chargeback report generated:${NC}"
        echo -e "  ${CYAN}ID:${NC}     $report_id"
        echo -e "  ${CYAN}Period:${NC} Jan 2026"
        echo "$report_result" | jq '{total_cost, line_items: (.line_items | length)}' 2>/dev/null
        print_success "Report generated"
    else
        print_warning "Could not generate report"
        echo "$report_result" | jq -r '.detail // .' 2>/dev/null
    fi

    echo ""

    # Generate forecast
    print_step "Generating budget forecast..."
    echo ""

    forecast_result=$(admin_post "/api/v1/reports/forecast/generate" '{}')

    echo -e "${WHITE}Budget Forecast:${NC}"
    echo "$forecast_result" | jq '.' 2>/dev/null || echo "$forecast_result"

    print_success "Chargeback demo complete"
}

# ─────────────────────────────────────────────
# Demo: SLA Monitoring
# ─────────────────────────────────────────────

demo_sla() {
    print_header "Demo: SLA Monitoring & Failover"

    print_info "Define SLAs, monitor provider health, configure automatic failover"
    echo ""

    admin_login || return 1

    # Create SLA definition
    print_step "Creating an SLA definition..."
    echo ""

    sla_result=$(admin_post "/api/v1/sla/definitions" '{
        "name": "Demo OpenAI GPT-4o SLA",
        "provider": "openai",
        "model_pattern": "gpt-4o*",
        "target_p50_ms": 500,
        "target_p95_ms": 2000,
        "target_p99_ms": 5000,
        "target_error_rate": 0.01,
        "target_availability": 0.999,
        "evaluation_window_minutes": 60,
        "alert_channels": ["slack"]
    }')

    sla_id=$(echo "$sla_result" | jq -r '.id // empty')

    if [ -n "$sla_id" ]; then
        echo -e "${WHITE}SLA definition created:${NC}"
        echo -e "  ${CYAN}ID:${NC}            $sla_id"
        echo -e "  ${CYAN}Provider:${NC}      openai"
        echo -e "  ${CYAN}Models:${NC}        gpt-4o*"
        echo -e "  ${CYAN}P95 target:${NC}    2000ms"
        echo -e "  ${CYAN}Error rate:${NC}    < 1%"
        echo -e "  ${CYAN}Availability:${NC}  99.9%"
        print_success "SLA created"
    else
        print_warning "Could not create SLA definition"
        echo "$sla_result" | jq -r '.detail // .' 2>/dev/null
    fi

    echo ""

    # Check provider health
    print_step "Checking provider health..."
    echo ""

    health=$(admin_get "/api/v1/sla/health")
    echo -e "${WHITE}Provider Health:${NC}"
    echo "$health" | jq '.' 2>/dev/null || echo "$health"
    echo ""

    # List violations
    print_step "Listing SLA violations..."
    echo ""

    violations=$(admin_get "/api/v1/sla/violations")
    violation_count=$(echo "$violations" | jq 'length' 2>/dev/null)
    echo -e "  Active violations: ${violation_count:-0}"
    echo ""

    # Create a failover rule
    print_step "Creating a failover rule..."
    echo ""

    failover_result=$(admin_post "/api/v1/sla/failover-rules" '{
        "name": "Demo GPT-4o Failover",
        "source_model": "gpt-4o",
        "target_model": "claude-3-5-sonnet",
        "trigger_condition": "error_rate > 0.05 OR p95_ms > 5000",
        "cooldown_minutes": 15
    }')

    failover_id=$(echo "$failover_result" | jq -r '.id // empty')

    if [ -n "$failover_id" ]; then
        echo -e "${WHITE}Failover rule created:${NC}"
        echo -e "  ${CYAN}Source:${NC}    gpt-4o"
        echo -e "  ${CYAN}Target:${NC}    claude-3-5-sonnet"
        echo -e "  ${CYAN}Trigger:${NC}   error_rate > 5% OR p95 > 5s"
        echo -e "  ${CYAN}Cooldown:${NC}  15 minutes"
        print_success "Failover rule created"
    else
        print_warning "Could not create failover rule"
        echo "$failover_result" | jq -r '.detail // .' 2>/dev/null
    fi

    print_success "SLA monitoring demo complete"
}

# ─────────────────────────────────────────────
# Demo: A/B Testing
# ─────────────────────────────────────────────

demo_abtests() {
    print_header "Demo: A/B Testing"

    print_info "Compare model performance with controlled traffic splitting"
    echo ""

    admin_login || return 1

    # List existing tests
    print_step "Listing existing A/B tests..."
    echo ""

    tests=$(admin_get "/api/v1/ab-tests")
    echo "$tests" | jq -r '.[] | "  \(.name) | \(.base_model) vs \(.variant_model) | \(.status)"' 2>/dev/null || echo "  No A/B tests found"
    echo ""

    # Create a new A/B test
    print_step "Creating an A/B test..."
    echo ""

    test_result=$(admin_post "/api/v1/ab-tests" '{
        "name": "Demo GPT-4o vs Claude Sonnet",
        "base_model": "gpt-4o",
        "variant_model": "claude-3-5-sonnet",
        "traffic_split_percent": 20,
        "success_metric": "cost_efficiency",
        "promotion_threshold": {
            "cost_efficiency": 0.05,
            "min_requests": 100
        },
        "rollback_threshold": {
            "error_rate": 0.10,
            "latency_increase_pct": 50
        },
        "auto_promote": false,
        "auto_rollback": true
    }')

    test_id=$(echo "$test_result" | jq -r '.id // empty')

    if [ -n "$test_id" ]; then
        echo -e "${WHITE}A/B test created:${NC}"
        echo -e "  ${CYAN}ID:${NC}        $test_id"
        echo -e "  ${CYAN}Base:${NC}      gpt-4o"
        echo -e "  ${CYAN}Variant:${NC}   claude-3-5-sonnet"
        echo -e "  ${CYAN}Split:${NC}     20% to variant"
        echo -e "  ${CYAN}Metric:${NC}    cost_efficiency"
        print_success "A/B test created"

        # Start the test
        echo ""
        print_step "Starting the A/B test..."
        echo ""

        start_result=$(admin_post "/api/v1/ab-tests/${test_id}/start" '{}')
        echo -e "  ${GREEN}Status: running${NC}"
        print_success "A/B test started"

        # Collect metrics
        echo ""
        print_step "Collecting metrics snapshot..."
        echo ""

        metrics_result=$(admin_post "/api/v1/ab-tests/${test_id}/collect-metrics" '{}')
        echo "$metrics_result" | jq '.' 2>/dev/null || echo "$metrics_result"
        print_success "Metrics collected"
    else
        print_warning "Could not create A/B test"
        echo "$test_result" | jq -r '.detail // .' 2>/dev/null
    fi

    print_success "A/B testing demo complete"
}

# ─────────────────────────────────────────────
# Demo: Event Subscriptions
# ─────────────────────────────────────────────

demo_events() {
    print_header "Demo: Event Subscriptions"

    print_info "Subscribe to platform events with webhook and Slack notifications"
    echo ""

    admin_login || return 1

    # List existing subscriptions
    print_step "Listing existing event subscriptions..."
    echo ""

    subs=$(admin_get "/api/v1/events/subscriptions")
    echo "$subs" | jq -r '.[] | "  \(.name) | \(.channel) | events=\(.event_types | join(", "))"' 2>/dev/null || echo "  No subscriptions found"
    echo ""

    # Create a subscription
    print_step "Creating a webhook event subscription..."
    echo ""

    sub_result=$(admin_post "/api/v1/events/subscriptions" '{
        "name": "Demo Budget Alerts",
        "event_types": ["budget.exceeded", "budget.warning", "sla.violation"],
        "channel": "webhook",
        "config": {
            "url": "https://httpbin.org/post",
            "secret": "demo-webhook-secret"
        }
    }')

    sub_id=$(echo "$sub_result" | jq -r '.id // empty')

    if [ -n "$sub_id" ]; then
        echo -e "${WHITE}Subscription created:${NC}"
        echo -e "  ${CYAN}ID:${NC}      $sub_id"
        echo -e "  ${CYAN}Channel:${NC} webhook"
        echo -e "  ${CYAN}Events:${NC}  budget.exceeded, budget.warning, sla.violation"
        print_success "Subscription created"
    else
        print_warning "Could not create subscription"
        echo "$sub_result" | jq -r '.detail // .' 2>/dev/null
    fi

    echo ""

    # Send a test event
    print_step "Sending a test event..."
    echo ""

    test_result=$(admin_post "/api/v1/events/test" '{
        "event_type": "budget.warning",
        "payload": {
            "team": "engineering",
            "current_spend": 4500,
            "budget_limit": 5000,
            "message": "Budget 90% utilized"
        }
    }')

    echo -e "${WHITE}Test Event Result:${NC}"
    echo "$test_result" | jq '.' 2>/dev/null || echo "$test_result"

    echo ""

    # View event log
    print_step "Viewing recent event log..."
    echo ""

    log=$(admin_get "/api/v1/events/log?limit=5")
    echo -e "${WHITE}Recent Events:${NC}"
    echo "$log" | jq -r '.[] | "  \(.timestamp // .created_at) | \(.event_type) | \(.status // "delivered")"' 2>/dev/null || echo "$log"

    print_success "Event subscriptions demo complete"
}

# ─────────────────────────────────────────────
# Demo: Audit Trail
# ─────────────────────────────────────────────

demo_audit() {
    print_header "Demo: Audit Trail"

    print_info "View and export audit logs for compliance and troubleshooting"
    echo ""

    admin_login || return 1

    # View recent audit logs
    print_step "Fetching recent audit logs..."
    echo ""

    logs=$(admin_get "/api/v1/audit-logs?limit=10")
    log_count=$(echo "$logs" | jq 'length' 2>/dev/null)

    echo -e "${WHITE}Recent Audit Entries: ${log_count:-0}${NC}"
    echo ""
    echo "$logs" | jq -r '.[] | "  \(.timestamp // .created_at) | \(.action) | \(.resource_type) | user=\(.user_id // "system")"' 2>/dev/null || echo "  No audit logs found"

    echo ""

    # Filter by action type
    print_step "Filtering audit logs by action type (create)..."
    echo ""

    filtered=$(admin_get "/api/v1/audit-logs?action=create&limit=5")
    filtered_count=$(echo "$filtered" | jq 'length' 2>/dev/null)

    echo -e "  Found ${filtered_count:-0} 'create' actions"
    echo "$filtered" | jq -r '.[] | "  \(.resource_type): \(.resource_id // "N/A")"' 2>/dev/null

    echo ""

    # Export
    print_step "Export available at:"
    echo ""
    echo -e "  ${BLUE}JSON:${NC} ${ADMIN_API}/api/v1/audit-logs/export?format=json"
    echo -e "  ${BLUE}CSV:${NC}  ${ADMIN_API}/api/v1/audit-logs/export?format=csv"

    print_success "Audit trail demo complete"
}

# ─────────────────────────────────────────────
# Demo: MCP Servers
# ─────────────────────────────────────────────

demo_mcp() {
    print_header "Demo: MCP Server Management"

    print_info "Configure and deploy Model Context Protocol servers"
    echo ""

    admin_login || return 1

    # List existing MCP servers
    print_step "Listing existing MCP servers..."
    echo ""

    servers=$(admin_get "/api/v1/mcp-servers")
    echo "$servers" | jq -r '.[] | "  \(.name) | type=\(.server_type) | active=\(.is_active // true)"' 2>/dev/null || echo "  No MCP servers found"
    echo ""

    # Create an MCP server
    print_step "Creating an MCP server configuration..."
    echo ""

    server_result=$(admin_post "/api/v1/mcp-servers" '{
        "name": "demo-filesystem",
        "server_type": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        "env": {}
    }')

    server_id=$(echo "$server_result" | jq -r '.id // empty')

    if [ -n "$server_id" ]; then
        echo -e "${WHITE}MCP server created:${NC}"
        echo -e "  ${CYAN}ID:${NC}      $server_id"
        echo -e "  ${CYAN}Name:${NC}    demo-filesystem"
        echo -e "  ${CYAN}Type:${NC}    stdio"
        echo -e "  ${CYAN}Command:${NC} npx -y @modelcontextprotocol/server-filesystem /tmp"
        print_success "Server created"

        # Test connectivity
        echo ""
        print_step "Testing server connectivity..."
        echo ""

        test_result=$(admin_post "/api/v1/mcp-servers/${server_id}/test" '{}')
        echo "$test_result" | jq '.' 2>/dev/null || echo "$test_result"

        # Preview Agent Gateway config
        echo ""
        print_step "Previewing Agent Gateway config..."
        echo ""

        preview=$(admin_get "/api/v1/mcp-servers/sync/preview")
        echo -e "${WHITE}Generated config:${NC}"
        echo "$preview" | jq '.' 2>/dev/null || echo "$preview"
    else
        print_warning "Could not create MCP server"
        echo "$server_result" | jq -r '.detail // .' 2>/dev/null
    fi

    print_success "MCP servers demo complete"
}

# ─────────────────────────────────────────────
# Demo: A2A Agents
# ─────────────────────────────────────────────

demo_a2a() {
    print_header "Demo: A2A Agent Management"

    print_info "Configure Agent-to-Agent communication endpoints"
    echo ""

    admin_login || return 1

    # List existing agents
    print_step "Listing existing A2A agents..."
    echo ""

    agents=$(admin_get "/api/v1/agents")
    echo "$agents" | jq -r '.[] | "  \(.name) | \(.url) | skills=\(.skills | join(", "))"' 2>/dev/null || echo "  No A2A agents found"
    echo ""

    # Create an A2A agent
    print_step "Creating an A2A agent configuration..."
    echo ""

    agent_result=$(admin_post "/api/v1/agents" '{
        "name": "demo-research-agent",
        "description": "Demo web research and summarization agent",
        "url": "http://research-agent:8080",
        "skills": ["web-search", "summarize", "fact-check"]
    }')

    agent_id=$(echo "$agent_result" | jq -r '.id // empty')

    if [ -n "$agent_id" ]; then
        echo -e "${WHITE}A2A agent created:${NC}"
        echo -e "  ${CYAN}ID:${NC}       $agent_id"
        echo -e "  ${CYAN}Name:${NC}     demo-research-agent"
        echo -e "  ${CYAN}URL:${NC}      http://research-agent:8080"
        echo -e "  ${CYAN}Skills:${NC}   web-search, summarize, fact-check"
        print_success "Agent created"
    else
        print_warning "Could not create agent"
        echo "$agent_result" | jq -r '.detail // .' 2>/dev/null
    fi

    echo ""

    # List agents to confirm
    print_step "Confirming agent list..."
    echo ""

    agents=$(admin_get "/api/v1/agents")
    agent_count=$(echo "$agents" | jq 'length' 2>/dev/null)
    echo -e "  Total registered agents: ${agent_count:-0}"

    print_success "A2A agents demo complete"
}

# ─────────────────────────────────────────────
# Demo: Model Deprecation
# ─────────────────────────────────────────────

demo_deprecation() {
    print_header "Demo: Model Deprecation Notices"

    print_info "Track model deprecations and manage migration timelines"
    echo ""

    admin_login || return 1

    # List existing deprecations
    print_step "Listing existing deprecation notices..."
    echo ""

    deprecations=$(admin_get "/api/v1/model-deprecations")
    echo "$deprecations" | jq -r '.[] | "  \(.model_name) -> \(.replacement_model) | sunset=\(.sunset_date)"' 2>/dev/null || echo "  No deprecations found"
    echo ""

    # Create a deprecation notice
    print_step "Creating a deprecation notice..."
    echo ""

    dep_result=$(admin_post "/api/v1/model-deprecations" '{
        "model_name": "gpt-4-turbo-preview",
        "replacement_model": "gpt-4o",
        "deprecation_date": "2026-03-01",
        "sunset_date": "2026-06-01",
        "message": "gpt-4-turbo-preview is deprecated. Migrate to gpt-4o for better performance and lower cost."
    }')

    dep_id=$(echo "$dep_result" | jq -r '.id // empty')

    if [ -n "$dep_id" ]; then
        echo -e "${WHITE}Deprecation notice created:${NC}"
        echo -e "  ${CYAN}ID:${NC}          $dep_id"
        echo -e "  ${CYAN}Model:${NC}       gpt-4-turbo-preview"
        echo -e "  ${CYAN}Replacement:${NC} gpt-4o"
        echo -e "  ${CYAN}Deprecated:${NC}  2026-03-01"
        echo -e "  ${CYAN}Sunset:${NC}      2026-06-01"
        print_success "Deprecation notice created"
    else
        print_warning "Could not create deprecation notice"
        echo "$dep_result" | jq -r '.detail // .' 2>/dev/null
    fi

    echo ""

    # Check model status
    print_step "Checking model deprecation status..."
    echo ""

    check=$(admin_get "/api/v1/model-deprecations/check/gpt-4-turbo-preview")
    echo -e "${WHITE}Model Status:${NC}"
    echo "$check" | jq '.' 2>/dev/null || echo "$check"

    print_success "Model deprecation demo complete"
}

# ─────────────────────────────────────────────
# Demo: Vault Secrets
# ─────────────────────────────────────────────

demo_vault() {
    print_header "Demo: Vault Secrets Management"

    print_info "HashiCorp Vault for secure secrets storage"
    echo ""

    export VAULT_ADDR=http://localhost:8200
    export VAULT_TOKEN="$VAULT_TOKEN"

    print_step "Checking Vault status..."
    echo ""

    health=$(curl -s http://localhost:8200/v1/sys/health)
    initialized=$(echo "$health" | jq -r '.initialized')
    sealed=$(echo "$health" | jq -r '.sealed')
    version=$(echo "$health" | jq -r '.version')

    echo -e "  ${CYAN}Initialized:${NC} $initialized"
    echo -e "  ${CYAN}Sealed:${NC}      $sealed"
    echo -e "  ${CYAN}Version:${NC}     $version"
    echo ""

    if [ "$sealed" = "true" ]; then
        print_error "Vault is sealed. Cannot read secrets."
        return 1
    fi

    # List available secret paths
    print_step "Available secret paths..."
    echo ""

    environments=("dev" "staging" "production")

    echo -e "${WHITE}Select environment to view:${NC}"
    local i=1
    for env in "${environments[@]}"; do
        echo -e "  ${WHITE}$i)${NC} $env"
        ((i++))
    done
    echo ""

    while true; do
        echo -ne "${CYAN}Select environment (1-${#environments[@]})${NC}: "
        read -r choice || true

        if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#environments[@]}" ]; then
            selected_env="${environments[$((choice-1))]}"
            break
        fi
        echo -e "${RED}Invalid choice.${NC}"
    done

    vault_path="secret/ai-gateway/$selected_env"

    echo ""
    print_step "Listing secrets at $vault_path..."
    echo ""

    secrets=$(curl -s "http://localhost:8200/v1/secret/metadata/ai-gateway/$selected_env" \
        -H "X-Vault-Token: $VAULT_TOKEN" \
        --request LIST 2>/dev/null)

    keys=$(echo "$secrets" | jq -r '.data.keys[]?' 2>/dev/null)

    if [ -n "$keys" ]; then
        echo -e "${WHITE}Secret paths:${NC}"
        echo "$keys" | while read -r key; do
            echo -e "  ${GREEN}•${NC} $vault_path/$key"
        done

        echo ""
        echo -ne "${CYAN}View a specific secret? Enter path (or press Enter to skip)${NC}: "
        read -r secret_path || true

        if [ -n "$secret_path" ]; then
            echo ""
            print_step "Reading secret: $vault_path/$secret_path"

            secret_data=$(curl -s "http://localhost:8200/v1/secret/data/ai-gateway/$selected_env/$secret_path" \
                -H "X-Vault-Token: $VAULT_TOKEN" 2>/dev/null)

            echo ""
            echo -e "${WHITE}Secret data (keys only for security):${NC}"
            echo "$secret_data" | jq '.data.data | keys' 2>/dev/null
        fi
    else
        print_warning "No secrets found at $vault_path"
        echo "Run: ENVIRONMENT=$selected_env ./scripts/vault-init.sh"
    fi

    print_success "Vault demo complete"
}

# ─────────────────────────────────────────────
# Demo: Observability
# ─────────────────────────────────────────────

demo_observability() {
    print_header "Demo: Observability Stack"

    print_info "Metrics, traces, and dashboards for full-stack visibility"
    echo ""

    print_step "Checking observability services..."
    echo ""

    check_service "http://localhost:9090/-/healthy" "Prometheus"
    check_service "http://localhost:3030/api/health" "Grafana"
    check_service "http://localhost:16686/" "Jaeger"

    echo ""
    echo -e "${WHITE}Service URLs:${NC}"
    echo ""
    echo -e "  ${BLUE}Grafana:${NC}    http://localhost:3030  (admin/admin)"
    echo -e "  ${BLUE}Prometheus:${NC} http://localhost:9090"
    echo -e "  ${BLUE}Jaeger:${NC}     http://localhost:16686"
    echo ""

    print_step "Sample Prometheus queries:"
    echo ""
    echo -e "  ${WHITE}Request rate:${NC}"
    echo -e "  ${CYAN}rate(litellm_requests_total[5m])${NC}"
    echo ""
    echo -e "  ${WHITE}Latency p95:${NC}"
    echo -e "  ${CYAN}histogram_quantile(0.95, rate(litellm_request_duration_seconds_bucket[5m]))${NC}"
    echo ""
    echo -e "  ${WHITE}Error rate:${NC}"
    echo -e "  ${CYAN}rate(litellm_requests_total{status=\"error\"}[5m]) / rate(litellm_requests_total[5m])${NC}"
    echo ""
    echo -e "  ${WHITE}Token throughput:${NC}"
    echo -e "  ${CYAN}sum(rate(litellm_tokens_total[5m])) by (model)${NC}"
    echo ""

    echo -ne "${CYAN}Open Grafana in browser? (y/n)${NC}: "
    read -r open_grafana || true

    if [[ "$open_grafana" =~ ^[Yy] ]]; then
        if command -v open &> /dev/null; then
            open http://localhost:3030
        elif command -v xdg-open &> /dev/null; then
            xdg-open http://localhost:3030
        fi
    fi

    print_success "Observability demo complete"
}

# ─────────────────────────────────────────────
# Demo: End-to-End Flow
# ─────────────────────────────────────────────

demo_e2e() {
    print_header "Demo: End-to-End Flow"

    print_info "Complete flow: Cost Predict -> Routing -> Chat -> Audit"
    echo ""

    # Get user inputs
    echo -ne "${CYAN}Enter your prompt${NC}: "
    read -r user_prompt || true

    if [ -z "$user_prompt" ]; then
        user_prompt="Explain the benefits of AI gateways for enterprises"
    fi

    echo ""

    # Step 1: Cost prediction
    print_step "Step 1: Predicting cost across models..."
    echo ""

    models_list=$(fetch_models)
    IFS=$'\n' read -r -d '' -a models_array <<< "$models_list" || true

    echo -e "${WHITE}Model                          Est. Cost${NC}"
    echo -e "─────────────────────────────────────────"

    for model in "${models_array[@]:0:5}"; do  # First 5 models
        cost=$(curl -s ${COST_PREDICTOR_API}/predict \
            -H "Content-Type: application/json" \
            -d "{
                \"model\": \"$model\",
                \"messages\": [{\"role\": \"user\", \"content\": \"$user_prompt\"}],
                \"max_tokens\": 500
            }" | jq -r '.total_estimated_cost_usd // "N/A"' 2>/dev/null)

        printf "  %-28s \$%s\n" "$model" "$cost"
    done

    wait_for_enter

    # Step 2: Check routing policies
    admin_login || return 1

    print_step "Step 2: Checking routing policies..."
    echo ""

    policies=$(admin_get "/api/v1/routing-policies")
    policy_count=$(echo "$policies" | jq 'length' 2>/dev/null)
    echo -e "  Active routing policies: ${policy_count:-0}"
    echo "$policies" | jq -r '.[] | "  \(.policy_type): \(.name)"' 2>/dev/null
    echo ""

    # Pick a model
    selected_model="${models_array[0]:-gpt-4o-mini}"

    wait_for_enter

    # Step 3: Execute request
    print_step "Step 3: Executing chat completion with $selected_model..."
    echo ""

    start_time=$(date +%s%N 2>/dev/null || python3 -c 'import time; print(int(time.time()*1e9))')

    response=$(curl -s ${LITELLM_API}/v1/chat/completions \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $LITELLM_KEY" \
        -d "{
            \"model\": \"$selected_model\",
            \"messages\": [{\"role\": \"user\", \"content\": \"$user_prompt\"}],
            \"max_tokens\": 500
        }")

    end_time=$(date +%s%N 2>/dev/null || python3 -c 'import time; print(int(time.time()*1e9))')
    duration=$(( (end_time - start_time) / 1000000 ))

    content=$(echo "$response" | jq -r '.choices[0].message.content // empty')

    if [ -n "$content" ] && [ "$content" != "null" ]; then
        echo -e "${WHITE}AI Response:${NC}"
        echo -e "${GREEN}$content${NC}"
        echo ""

        tokens=$(echo "$response" | jq '.usage.total_tokens // 0')
        echo -e "  ${CYAN}Tokens used:${NC}  $tokens"
        echo -e "  ${CYAN}Latency:${NC}      ${duration}ms"

        print_success "Request completed successfully"
    else
        print_error "Request failed"
    fi

    wait_for_enter

    # Step 4: Check audit trail
    print_step "Step 4: Checking audit trail..."
    echo ""

    logs=$(admin_get "/api/v1/audit-logs?limit=5")
    echo -e "${WHITE}Recent Audit Entries:${NC}"
    echo "$logs" | jq -r '.[] | "  \(.timestamp // .created_at) | \(.action) | \(.resource_type)"' 2>/dev/null || echo "  No audit entries"

    echo ""

    # Step 5: Observability links
    print_step "Step 5: View in observability tools..."
    echo ""
    echo -e "  ${BLUE}Grafana:${NC}    http://localhost:3030  (admin/admin)"
    echo -e "  ${BLUE}Prometheus:${NC} http://localhost:9090"
    echo -e "  ${BLUE}Jaeger:${NC}     http://localhost:16686"

    print_success "End-to-end demo complete!"
}

# ─────────────────────────────────────────────
# Demo: Admin UI
# ─────────────────────────────────────────────

demo_ui() {
    print_header "Demo: Admin Dashboard"

    print_info "Web UI for full platform configuration and monitoring"
    echo ""

    echo -e "${WHITE}Admin UI Details:${NC}"
    echo ""
    echo -e "  ${BLUE}URL:${NC}      http://localhost:5173"
    echo -e "  ${BLUE}API Key:${NC}  $LITELLM_KEY"
    echo ""
    echo -e "${WHITE}Available sections (20):${NC}"
    echo ""
    echo -e "  ${GREEN}•${NC} Dashboard       - Real-time metrics and status"
    echo -e "  ${GREEN}•${NC} Models          - Model configuration and routing"
    echo -e "  ${GREEN}•${NC} API Keys        - Key generation and management"
    echo -e "  ${GREEN}•${NC} Teams           - Team management and members"
    echo -e "  ${GREEN}•${NC} Budgets         - Spending limits by team/user"
    echo -e "  ${GREEN}•${NC} Organizations   - Multi-tenant org hierarchy"
    echo -e "  ${GREEN}•${NC} Audit Log       - Compliance and activity tracking"
    echo -e "  ${GREEN}•${NC} Prompts         - Versioned prompt template registry"
    echo -e "  ${GREEN}•${NC} Rate Limits     - Per-team and per-model rate policies"
    echo -e "  ${GREEN}•${NC} Model Access    - Tiered access with approval workflows"
    echo -e "  ${GREEN}•${NC} Chargeback      - Cost allocation and reports"
    echo -e "  ${GREEN}•${NC} SLA Monitor     - Provider health and failover rules"
    echo -e "  ${GREEN}•${NC} A/B Tests       - Model comparison experiments"
    echo -e "  ${GREEN}•${NC} Events          - Event subscriptions and webhooks"
    echo -e "  ${GREEN}•${NC} Routing         - Fallback, model group, and strategy policies"
    echo -e "  ${GREEN}•${NC} MCP Servers     - Model Context Protocol server config"
    echo -e "  ${GREEN}•${NC} A2A Agents      - Agent-to-Agent communication"
    echo -e "  ${GREEN}•${NC} Guardrails      - Content safety and DLP"
    echo -e "  ${GREEN}•${NC} Workflows       - LangGraph workflow templates"
    echo -e "  ${GREEN}•${NC} Settings        - Platform configuration"
    echo ""

    echo -ne "${CYAN}Open in browser? (y/n)${NC}: "
    read -r open_browser || true

    if [[ "$open_browser" =~ ^[Yy] ]]; then
        if command -v open &> /dev/null; then
            open http://localhost:5173
        elif command -v xdg-open &> /dev/null; then
            xdg-open http://localhost:5173
        fi
    fi

    print_success "Admin UI demo complete"
}

# ─────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────

show_summary() {
    print_header "Demo Summary"

    echo -e "${WHITE}Service Endpoints:${NC}"
    echo ""
    printf "  %-20s %s\n" "Landing Page:" "http://localhost:9999"
    printf "  %-20s %s\n" "Admin UI:" "http://localhost:5173"
    printf "  %-20s %s\n" "Admin API:" "http://localhost:8086"
    printf "  %-20s %s\n" "LiteLLM API:" "http://localhost:4000"
    printf "  %-20s %s\n" "Workflow Engine:" "http://localhost:8085"
    printf "  %-20s %s\n" "A2A Runtime:" "http://localhost:8087"
    printf "  %-20s %s\n" "Cost Predictor:" "http://localhost:8080"
    printf "  %-20s %s\n" "Agent Gateway:" "http://localhost:9000"
    printf "  %-20s %s\n" "Grafana:" "http://localhost:3030"
    printf "  %-20s %s\n" "Prometheus:" "http://localhost:9090"
    printf "  %-20s %s\n" "Jaeger:" "http://localhost:16686"
    printf "  %-20s %s\n" "Vault:" "http://localhost:8200"
    echo ""

    print_success "Demo complete!"
}

# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

main() {
    local scenario="${1:-all}"

    echo ""
    echo -e "${PURPLE}    _    ___    ____       _                           ${NC}"
    echo -e "${PURPLE}   / \  |_ _|  / ___| __ _| |_ _____      ____ _ _   _ ${NC}"
    echo -e "${PURPLE}  / _ \  | |  | |  _ / _\` | __/ _ \ \ /\ / / _\` | | | |${NC}"
    echo -e "${PURPLE} / ___ \ | |  | |_| | (_| | ||  __/\ V  V / (_| | |_| |${NC}"
    echo -e "${PURPLE}/_/   \_\___|  \____|\__,_|\__\___| \_/\_/ \__,_|\__, |${NC}"
    echo -e "${PURPLE}                                                 |___/ ${NC}"
    echo -e "${WHITE}              Interactive Demo${NC}"
    echo ""

    case "$scenario" in
        status)
            demo_status
            ;;
        chat)
            demo_status
            demo_chat
            ;;
        cost)
            demo_status
            demo_cost
            ;;
        routing)
            demo_status
            demo_routing
            ;;
        cache)
            demo_status
            demo_cache
            ;;
        workflow)
            demo_status
            demo_workflow
            ;;
        orgs)
            demo_status
            demo_orgs
            ;;
        guardrails)
            demo_status
            demo_guardrails
            ;;
        prompts)
            demo_status
            demo_prompts
            ;;
        ratelimits)
            demo_status
            demo_ratelimits
            ;;
        access)
            demo_status
            demo_access
            ;;
        chargeback)
            demo_status
            demo_chargeback
            ;;
        sla)
            demo_status
            demo_sla
            ;;
        abtests)
            demo_status
            demo_abtests
            ;;
        events)
            demo_status
            demo_events
            ;;
        audit)
            demo_status
            demo_audit
            ;;
        mcp)
            demo_status
            demo_mcp
            ;;
        a2a)
            demo_status
            demo_a2a
            ;;
        deprecation)
            demo_status
            demo_deprecation
            ;;
        vault)
            demo_status
            demo_vault
            ;;
        observability)
            demo_status
            demo_observability
            ;;
        e2e)
            demo_status
            demo_e2e
            ;;
        ui)
            demo_status
            demo_ui
            ;;
        all)
            demo_status
            wait_for_enter
            demo_chat
            wait_for_enter
            demo_cost
            wait_for_enter
            demo_routing
            wait_for_enter
            demo_cache
            wait_for_enter
            demo_workflow
            wait_for_enter
            demo_orgs
            wait_for_enter
            demo_guardrails
            wait_for_enter
            demo_prompts
            wait_for_enter
            demo_ratelimits
            wait_for_enter
            demo_access
            wait_for_enter
            demo_chargeback
            wait_for_enter
            demo_sla
            wait_for_enter
            demo_abtests
            wait_for_enter
            demo_events
            wait_for_enter
            demo_audit
            wait_for_enter
            demo_mcp
            wait_for_enter
            demo_a2a
            wait_for_enter
            demo_deprecation
            wait_for_enter
            demo_vault
            wait_for_enter
            demo_observability
            wait_for_enter
            demo_e2e
            wait_for_enter
            demo_ui
            ;;
        *)
            echo "Usage: $0 [scenario]"
            echo ""
            echo "Scenarios:"
            echo "  all           - Run all demos (default)"
            echo "  status        - Check service health"
            echo "  chat          - Interactive AI chat"
            echo "  cost          - Cost prediction with model comparison"
            echo "  routing       - Routing policies (fallback, model groups, strategies)"
            echo "  cache         - Semantic cache via LiteLLM"
            echo "  workflow      - Workflow execution with templates"
            echo "  orgs          - Organizations, business units, members"
            echo "  guardrails    - Guardrails & DLP content detection"
            echo "  prompts       - Prompt registry with versioning & approval"
            echo "  ratelimits    - Rate limit policies & pre-flight checks"
            echo "  access        - Model access tiers & approval workflow"
            echo "  chargeback    - Cost allocation, reports, forecasting"
            echo "  sla           - SLA monitoring, health, failover rules"
            echo "  abtests       - A/B testing with traffic splitting"
            echo "  events        - Event subscriptions & webhooks"
            echo "  audit         - Audit trail & log export"
            echo "  mcp           - MCP server management & deployment"
            echo "  a2a           - A2A agent configuration"
            echo "  deprecation   - Model deprecation notices"
            echo "  vault         - Secrets management"
            echo "  observability - Observability stack (Grafana, Prometheus, Jaeger)"
            echo "  e2e           - End-to-end flow"
            echo "  ui            - Admin dashboard"
            exit 1
            ;;
    esac

    show_summary
}

main "$@"
