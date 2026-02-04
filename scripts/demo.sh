#!/bin/bash
#
# AI Gateway Interactive Demo Script
#
# Usage: ./scripts/demo.sh [scenario]
#
# Scenarios:
#   all       - Run all demos (default)
#   chat      - Basic AI chat
#   cost      - Cost prediction
#   routing   - Policy-based routing
#   workflow  - Workflow engine
#   cache     - Semantic cache
#   vault     - Secrets management
#   e2e       - End-to-end flow
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

# Helper functions
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

    if curl -s -o /dev/null -w "%{http_code}" "$url" | grep -q "200\|204"; then
        echo -e "  ${GREEN}✓${NC} $name"
        return 0
    else
        echo -e "  ${RED}✗${NC} $name"
        return 1
    fi
}

# Fetch real data functions
fetch_models() {
    curl -s http://localhost:4000/v1/models \
        -H "Authorization: Bearer $LITELLM_KEY" | jq -r '.data[].id' 2>/dev/null
}

fetch_teams() {
    curl -s http://localhost:8086/api/v1/teams \
        -H "Authorization: Bearer $LITELLM_KEY" | jq -r '.[].name' 2>/dev/null
}

fetch_workflow_templates() {
    curl -s http://localhost:8085/api/v1/templates | jq -r '.templates[].type // .[] | if type == "object" then .type else . end' 2>/dev/null
}

fetch_budgets() {
    curl -s http://localhost:8086/api/v1/budgets \
        -H "Authorization: Bearer $LITELLM_KEY" | jq -r '.[].name' 2>/dev/null
}

# Demo functions
demo_status() {
    print_header "🔍 Platform Status Check"

    print_step "Checking service health..."
    echo ""

    local healthy=0
    local total=0

    services=(
        "http://localhost:4000/health/liveliness|LiteLLM (AI Proxy)"
        "http://localhost:8084/health|Policy Router"
        "http://localhost:8085/health|Workflow Engine"
        "http://localhost:8080/health|Cost Predictor"
        "http://localhost:8081/health|Budget Webhook"
        "http://localhost:8083/health|Semantic Cache"
        "http://localhost:8086/health|Admin API"
        "http://localhost:5173|Admin UI"
        "http://localhost:9090/-/healthy|Prometheus"
        "http://localhost:3030/api/health|Grafana"
        "http://localhost:8200/v1/sys/health|Vault"
        "http://localhost:9000/healthz|Agent Gateway"
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

demo_chat() {
    print_header "💬 Demo 1: AI Chat Completion"

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
    response=$(curl -s http://localhost:4000/v1/chat/completions \
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
        usage=$(echo "$response" | jq '.usage' 2>/dev/null)
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

demo_cost() {
    print_header "💰 Demo 2: Cost Prediction"

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

    prediction=$(curl -s http://localhost:8080/predict \
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
            cost=$(curl -s http://localhost:8080/predict \
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

demo_routing() {
    print_header "🔀 Demo 3: Policy-Based Model Routing"

    print_info "Cedar policies select optimal model based on budget, latency, and team"
    echo ""

    # Get user inputs
    echo -ne "${CYAN}User ID${NC} [demo-user]: "
    read -r user_id || true
    user_id=${user_id:-demo-user}

    # Fetch teams if available
    teams_list=$(fetch_teams 2>/dev/null) || true
    if [ -n "$teams_list" ]; then
        echo ""
        echo -e "${WHITE}Available teams:${NC}"
        IFS=$'\n' read -r -d '' -a teams_array <<< "$teams_list" || true
        local i=1
        for team in "${teams_array[@]}"; do
            echo -e "  ${WHITE}$i)${NC} $team"
            i=$((i + 1))
        done
        echo -e "  ${WHITE}$i)${NC} (enter custom)"
        echo ""

        echo -ne "${CYAN}Select team${NC}: "
        read -r team_choice || true

        if [[ "$team_choice" =~ ^[0-9]+$ ]] && [ "$team_choice" -ge 1 ] && [ "$team_choice" -lt "$i" ]; then
            team_id="${teams_array[$((team_choice-1))]}"
        else
            echo -ne "${CYAN}Enter team name${NC}: "
            read -r team_id || true
        fi
    else
        echo -ne "${CYAN}Team ID${NC} [engineering]: "
        read -r team_id || true
    fi
    team_id=${team_id:-engineering}

    echo -ne "${CYAN}Budget remaining (USD)${NC} [50.0]: "
    read -r budget || true
    budget=${budget:-50.0}

    echo -ne "${CYAN}Latency SLA (ms)${NC} [1000]: "
    read -r latency_sla || true
    latency_sla=${latency_sla:-1000}

    echo ""
    print_step "Requesting model routing decision..."
    echo ""

    route_result=$(curl -s http://localhost:8084/route \
        -H "Content-Type: application/json" \
        -d "{
            \"user_id\": \"$user_id\",
            \"team_id\": \"$team_id\",
            \"requested_model\": \"smart\",
            \"budget_remaining\": $budget,
            \"latency_sla_ms\": $latency_sla
        }")

    selected=$(echo "$route_result" | jq -r '.selected_model // "N/A"')
    fallbacks=$(echo "$route_result" | jq -r '.fallback_models // [] | join(", ")' 2>/dev/null)
    reason=$(echo "$route_result" | jq -r '.decision_reason // "N/A"')

    echo -e "${WHITE}Routing Decision:${NC}"
    echo ""
    echo -e "  ${GREEN}Selected Model:${NC}  $selected"
    echo -e "  ${CYAN}Fallbacks:${NC}       $fallbacks"
    echo -e "  ${BLUE}Reason:${NC}          $reason"
    echo ""

    # Test with different scenarios
    echo -ne "${CYAN}Test another scenario? (y/n)${NC}: "
    read -r again || true

    if [[ "$again" =~ ^[Yy] ]]; then
        demo_routing
    fi
}

demo_workflow() {
    print_header "⚙️ Demo 4: Workflow Engine"

    print_info "LangGraph-powered multi-step AI workflows"
    echo ""

    # Fetch available templates
    print_step "Fetching workflow templates..."
    echo ""

    templates_response=$(curl -s http://localhost:8085/api/v1/templates)

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

    execution=$(curl -s http://localhost:8085/api/v1/executions \
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

demo_cache() {
    print_header "🗃️ Demo 5: Semantic Cache"

    print_info "Intelligent caching based on semantic similarity"
    echo ""

    # Fetch models
    print_step "Fetching available models..."
    models_list=$(fetch_models)
    IFS=$'\n' read -r -d '' -a models_array <<< "$models_list" || true

    echo ""
    echo -e "${WHITE}Select model for caching:${NC}"
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
    echo -ne "${CYAN}Enter a query to cache${NC}: "
    read -r original_query || true

    if [ -z "$original_query" ]; then
        original_query="What is machine learning?"
    fi

    echo ""
    print_step "First, let's make a real API call and cache the response..."
    echo ""

    # Make actual LLM call
    response=$(curl -s http://localhost:4000/v1/chat/completions \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $LITELLM_KEY" \
        -d "{
            \"model\": \"$selected_model\",
            \"messages\": [{\"role\": \"user\", \"content\": \"$original_query\"}],
            \"max_tokens\": 200
        }")

    content=$(echo "$response" | jq -r '.choices[0].message.content // empty')
    input_tokens=$(echo "$response" | jq -r '.usage.prompt_tokens // 0')
    output_tokens=$(echo "$response" | jq -r '.usage.completion_tokens // 0')

    if [ -n "$content" ] && [ "$content" != "null" ]; then
        echo -e "${WHITE}Response:${NC}"
        echo -e "${GREEN}$content${NC}"
        echo ""

        # Store in cache
        print_step "Storing response in semantic cache..."

        # Escape content for JSON
        escaped_content=$(echo "$content" | jq -Rs .)

        store_result=$(curl -s http://localhost:8083/store \
            -H "Content-Type: application/json" \
            -H "Authorization: Bearer $LITELLM_KEY" \
            -d "{
                \"messages\": [{\"role\": \"user\", \"content\": \"$original_query\"}],
                \"model\": \"$selected_model\",
                \"response\": {\"choices\": [{\"message\": {\"role\": \"assistant\", \"content\": $escaped_content}}]},
                \"input_tokens\": $input_tokens,
                \"output_tokens\": $output_tokens
            }")

        echo "$store_result" | jq '.' 2>/dev/null
        print_success "Response cached"
    else
        print_error "Could not get LLM response"
        return 1
    fi

    echo ""
    echo -ne "${CYAN}Now enter a similar query to test cache hit${NC}: "
    read -r similar_query || true

    if [ -z "$similar_query" ]; then
        similar_query="Explain machine learning"
    fi

    echo ""
    print_step "Looking up similar query in cache..."
    echo ""

    lookup_result=$(curl -s http://localhost:8083/lookup \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $LITELLM_KEY" \
        -d "{
            \"messages\": [{\"role\": \"user\", \"content\": \"$similar_query\"}],
            \"model\": \"$selected_model\"
        }")

    hit=$(echo "$lookup_result" | jq -r '.hit // false')
    similarity=$(echo "$lookup_result" | jq -r '.similarity // "N/A"')

    if [ "$hit" = "true" ]; then
        print_success "Cache HIT!"
        echo -e "  ${CYAN}Similarity:${NC} $similarity"
        cached_response=$(echo "$lookup_result" | jq -r '.response.choices[0].message.content // empty')
        if [ -n "$cached_response" ]; then
            echo ""
            echo -e "${WHITE}Cached Response:${NC}"
            echo -e "${GREEN}$cached_response${NC}"
        fi
    else
        print_info "Cache MISS (similarity below threshold)"
        echo -e "  This would trigger a new API call"
    fi

    echo ""
    print_step "Cache statistics..."
    stats=$(curl -s http://localhost:8083/stats)
    echo ""
    echo -e "${WHITE}Cache Stats:${NC}"
    echo "$stats" | jq '.' 2>/dev/null
}

demo_vault() {
    print_header "🔐 Demo 6: Vault Secrets Management"

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

demo_e2e() {
    print_header "🚀 Demo 7: End-to-End Flow"

    print_info "Complete flow: Cost Prediction → Routing → Execution → Observability"
    echo ""

    # Get user inputs
    echo -ne "${CYAN}Enter your prompt${NC}: "
    read -r user_prompt || true

    if [ -z "$user_prompt" ]; then
        user_prompt="Explain the benefits of AI gateways for enterprises"
    fi

    echo -ne "${CYAN}Your user ID${NC} [demo-user]: "
    read -r user_id || true
    user_id=${user_id:-demo-user}

    echo -ne "${CYAN}Team${NC} [engineering]: "
    read -r team_id || true
    team_id=${team_id:-engineering}

    echo -ne "${CYAN}Budget remaining (USD)${NC} [50.0]: "
    read -r budget || true
    budget=${budget:-50.0}

    echo ""

    # Step 1: Cost prediction
    print_step "Step 1: Predicting cost across models..."
    echo ""

    models_list=$(fetch_models)
    IFS=$'\n' read -r -d '' -a models_array <<< "$models_list" || true

    echo -e "${WHITE}Model                          Est. Cost${NC}"
    echo -e "─────────────────────────────────────────"

    for model in "${models_array[@]:0:5}"; do  # First 5 models
        cost=$(curl -s http://localhost:8080/predict \
            -H "Content-Type: application/json" \
            -d "{
                \"model\": \"$model\",
                \"messages\": [{\"role\": \"user\", \"content\": \"$user_prompt\"}],
                \"max_tokens\": 500
            }" | jq -r '.total_estimated_cost_usd // "N/A"' 2>/dev/null)

        printf "  %-28s \$%s\n" "$model" "$cost"
    done

    wait_for_enter

    # Step 2: Get routed model
    print_step "Step 2: Getting optimal model via policy router..."
    echo ""

    route_result=$(curl -s http://localhost:8084/route \
        -H "Content-Type: application/json" \
        -d "{
            \"user_id\": \"$user_id\",
            \"team_id\": \"$team_id\",
            \"requested_model\": \"smart\",
            \"budget_remaining\": $budget
        }")

    selected_model=$(echo "$route_result" | jq -r '.selected_model // "gpt-4o-mini"')
    reason=$(echo "$route_result" | jq -r '.decision_reason // "N/A"')

    echo -e "  ${GREEN}Selected:${NC} $selected_model"
    echo -e "  ${BLUE}Reason:${NC}   $reason"

    wait_for_enter

    # Step 3: Execute request
    print_step "Step 3: Executing chat completion with $selected_model..."
    echo ""

    start_time=$(date +%s%N)

    response=$(curl -s http://localhost:4000/v1/chat/completions \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $LITELLM_KEY" \
        -d "{
            \"model\": \"$selected_model\",
            \"messages\": [{\"role\": \"user\", \"content\": \"$user_prompt\"}],
            \"max_tokens\": 500
        }")

    end_time=$(date +%s%N)
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

    # Step 4: View observability
    print_step "Step 4: View in observability tools..."
    echo ""
    echo -e "  ${BLUE}Grafana:${NC}    http://localhost:3030  (admin/admin)"
    echo -e "  ${BLUE}Prometheus:${NC} http://localhost:9090"
    echo -e "  ${BLUE}Jaeger:${NC}     http://localhost:16686"
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

    print_success "End-to-end demo complete!"
}

demo_ui() {
    print_header "🖥️ Demo 8: Admin Dashboard"

    print_info "Web UI for platform configuration and monitoring"
    echo ""

    echo -e "${WHITE}Admin UI Details:${NC}"
    echo ""
    echo -e "  ${BLUE}URL:${NC}      http://localhost:5173"
    echo -e "  ${BLUE}API Key:${NC}  $LITELLM_KEY"
    echo ""
    echo -e "${WHITE}Available sections:${NC}"
    echo -e "  ${GREEN}•${NC} Dashboard - Real-time metrics and status"
    echo -e "  ${GREEN}•${NC} Models - Configure model routing and fallbacks"
    echo -e "  ${GREEN}•${NC} Budgets - Set spending limits by team/user"
    echo -e "  ${GREEN}•${NC} Teams - User and team management"
    echo -e "  ${GREEN}•${NC} MCP Servers - Tool configuration"
    echo -e "  ${GREEN}•${NC} Workflows - Manage workflow templates"
    echo -e "  ${GREEN}•${NC} Policies - Cedar policy editor"
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

show_summary() {
    print_header "📊 Demo Summary"

    echo -e "${WHITE}Service Endpoints:${NC}"
    echo ""
    printf "  %-20s %s\n" "Landing Page:" "http://localhost:9999"
    printf "  %-20s %s\n" "Admin UI:" "http://localhost:5173"
    printf "  %-20s %s\n" "LiteLLM API:" "http://localhost:4000"
    printf "  %-20s %s\n" "Policy Router:" "http://localhost:8084"
    printf "  %-20s %s\n" "Workflow Engine:" "http://localhost:8085"
    printf "  %-20s %s\n" "Cost Predictor:" "http://localhost:8080"
    printf "  %-20s %s\n" "Semantic Cache:" "http://localhost:8083"
    printf "  %-20s %s\n" "Grafana:" "http://localhost:3030"
    printf "  %-20s %s\n" "Prometheus:" "http://localhost:9090"
    printf "  %-20s %s\n" "Jaeger:" "http://localhost:16686"
    printf "  %-20s %s\n" "Vault:" "http://localhost:8200"
    echo ""

    print_success "Demo complete! 🎉"
}

# Main
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
        workflow)
            demo_status
            demo_workflow
            ;;
        cache)
            demo_status
            demo_cache
            ;;
        vault)
            demo_status
            demo_vault
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
            demo_workflow
            wait_for_enter
            demo_cache
            wait_for_enter
            demo_vault
            wait_for_enter
            demo_e2e
            wait_for_enter
            demo_ui
            ;;
        *)
            echo "Usage: $0 [scenario]"
            echo ""
            echo "Scenarios:"
            echo "  all       - Run all demos (default)"
            echo "  status    - Check service health"
            echo "  chat      - Interactive AI chat"
            echo "  cost      - Cost prediction with model selection"
            echo "  routing   - Policy-based routing with custom params"
            echo "  workflow  - Workflow execution with templates"
            echo "  cache     - Semantic cache demonstration"
            echo "  vault     - Secrets management"
            echo "  e2e       - End-to-end flow"
            echo "  ui        - Admin dashboard"
            exit 1
            ;;
    esac

    show_summary
}

main "$@"
