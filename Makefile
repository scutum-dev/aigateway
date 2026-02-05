# =============================================================================
# AI Gateway Platform - Makefile
# =============================================================================
# Cross-platform commands for development and deployment
# Works on: macOS, Linux, Windows (with make installed)
#
# Usage:
#   make help          - Show available commands
#   make up            - Start core services
#   make up-full       - Start all services
#   make down          - Stop all services
#   make logs          - View logs
# =============================================================================

.PHONY: help up down logs build clean test migrate demo staging prod destroy demo-destroy staging-destroy prod-destroy cloud-status cloud-output cloud-plan

# Default environment file
ENV_FILE ?= .env

# Docker Compose command (supports both v1 and v2)
DOCKER_COMPOSE := docker compose
ifeq ($(shell docker compose version 2>/dev/null),)
	DOCKER_COMPOSE := docker-compose
endif

# Colors for output (works on most terminals)
CYAN := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RESET := \033[0m

# =============================================================================
# HELP
# =============================================================================

help: ## Show this help message
	@echo "$(CYAN)AI Gateway Platform$(RESET)"
	@echo ""
	@echo "$(GREEN)Usage:$(RESET)"
	@echo "  make [target]"
	@echo ""
	@echo "$(GREEN)Targets:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(RESET) %s\n", $$1, $$2}'

# =============================================================================
# ENVIRONMENT SETUP
# =============================================================================

init: ## Initialize environment (copy .env.example to .env)
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "$(GREEN)Created .env from .env.example$(RESET)"; \
		echo "$(YELLOW)Please edit .env and add your API keys$(RESET)"; \
	else \
		echo "$(YELLOW).env already exists$(RESET)"; \
	fi

env-check: ## Verify environment configuration
	@echo "$(CYAN)Checking environment...$(RESET)"
	@test -f .env || (echo "$(YELLOW)Warning: .env not found, using defaults$(RESET)")
	@echo "Environment: $${ENVIRONMENT:-development}"
	@echo "LiteLLM Port: $${LITELLM_PORT:-4000}"
	@echo "Admin UI Port: $${ADMIN_UI_PORT:-5173}"

# =============================================================================
# DOCKER COMPOSE - CORE
# =============================================================================

up: ## Start core services (postgres, redis, litellm, admin)
	$(DOCKER_COMPOSE) up -d
	@echo "$(GREEN)Core services started$(RESET)"
	@echo "  Admin UI: http://localhost:$${ADMIN_UI_PORT:-5173}"
	@echo "  LiteLLM:  http://localhost:$${LITELLM_PORT:-4000}"

down: ## Stop all services
	$(DOCKER_COMPOSE) --profile full down
	@echo "$(GREEN)All services stopped$(RESET)"

restart: ## Restart all running services
	$(DOCKER_COMPOSE) restart

# =============================================================================
# DOCKER COMPOSE - PROFILES
# =============================================================================

up-full: ## Start ALL services (full stack)
	$(DOCKER_COMPOSE) --profile full up -d
	@echo "$(GREEN)Full stack started$(RESET)"

up-observability: ## Start core + observability (Prometheus, Grafana, Jaeger)
	$(DOCKER_COMPOSE) --profile observability up -d
	@echo "$(GREEN)Observability stack started$(RESET)"
	@echo "  Grafana:    http://localhost:$${GRAFANA_PORT:-3030}"
	@echo "  Prometheus: http://localhost:$${PROMETHEUS_PORT:-9090}"
	@echo "  Jaeger:     http://localhost:$${JAEGER_PORT:-16686}"

up-workflows: ## Start core + workflow engine (Temporal)
	$(DOCKER_COMPOSE) --profile workflows up -d
	@echo "$(GREEN)Workflow stack started$(RESET)"
	@echo "  Temporal UI: http://localhost:8088"

up-local-models: ## Start core + local model support (GPU stub)
	$(DOCKER_COMPOSE) --profile local-models up -d
	@echo "$(GREEN)Local models support started$(RESET)"

up-finops: ## Start core + FinOps services
	$(DOCKER_COMPOSE) --profile finops up -d
	@echo "$(GREEN)FinOps stack started$(RESET)"

up-experimental: ## Start core + experimental features
	$(DOCKER_COMPOSE) --profile experimental up -d
	@echo "$(GREEN)Experimental features started$(RESET)"

# =============================================================================
# BUILD
# =============================================================================

build: ## Build all custom images
	$(DOCKER_COMPOSE) --profile full build
	@echo "$(GREEN)All images built$(RESET)"

build-no-cache: ## Build all images without cache
	$(DOCKER_COMPOSE) --profile full build --no-cache

build-admin: ## Build admin-api and admin-ui
	$(DOCKER_COMPOSE) build admin-api admin-ui

# =============================================================================
# LOGS & STATUS
# =============================================================================

logs: ## View logs (all services)
	$(DOCKER_COMPOSE) logs -f

logs-litellm: ## View LiteLLM logs
	$(DOCKER_COMPOSE) logs -f litellm

logs-admin: ## View Admin API logs
	$(DOCKER_COMPOSE) logs -f admin-api

ps: ## Show running services
	$(DOCKER_COMPOSE) ps

status: ## Show service health status
	@echo "$(CYAN)Service Status:$(RESET)"
	@$(DOCKER_COMPOSE) ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

# =============================================================================
# DATABASE
# =============================================================================

migrate: ## Run database migrations
	$(DOCKER_COMPOSE) exec admin-api python -c "from alembic.config import Config; from alembic import command; cfg = Config('/app/alembic.ini'); cfg.set_main_option('script_location', '/app/alembic'); command.upgrade(cfg, 'head')"
	@echo "$(GREEN)Migrations completed$(RESET)"

db-shell: ## Connect to PostgreSQL shell
	$(DOCKER_COMPOSE) exec postgres psql -U $${POSTGRES_USER:-postgres} -d $${POSTGRES_DB:-litellm}

db-reset: ## Reset database (WARNING: destroys data)
	@echo "$(YELLOW)WARNING: This will destroy all data!$(RESET)"
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ]
	$(DOCKER_COMPOSE) down -v
	$(DOCKER_COMPOSE) up -d postgres
	@sleep 5
	$(DOCKER_COMPOSE) up -d
	@echo "$(GREEN)Database reset complete$(RESET)"

# =============================================================================
# TESTING
# =============================================================================

test: ## Run all tests
	cd tests && python -m pytest -v

test-integration: ## Run integration tests
	cd tests && python -m pytest integration/ -v

test-api: ## Test API endpoints
	@echo "$(CYAN)Testing LiteLLM health...$(RESET)"
	@curl -s http://localhost:4000/health/liveliness | jq .
	@echo "$(CYAN)Testing Admin API health...$(RESET)"
	@curl -s http://localhost:8086/health | jq .

# =============================================================================
# UTILITIES
# =============================================================================

clean: ## Remove all containers, volumes, and images
	$(DOCKER_COMPOSE) --profile full down -v --rmi local
	docker system prune -f
	@echo "$(GREEN)Cleanup complete$(RESET)"

shell-admin: ## Open shell in admin-api container
	$(DOCKER_COMPOSE) exec admin-api /bin/sh

shell-litellm: ## Open shell in litellm container
	$(DOCKER_COMPOSE) exec litellm /bin/bash

# =============================================================================
# DEPLOYMENT
# =============================================================================

deploy-dev: ## Deploy to Kubernetes (dev)
	kubectl apply -k kubernetes/overlays/dev

deploy-staging: ## Deploy to Kubernetes (staging)
	kubectl apply -k kubernetes/overlays/staging

deploy-prod: ## Deploy to Kubernetes (production)
	@echo "$(YELLOW)WARNING: Deploying to production!$(RESET)"
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ]
	kubectl apply -k kubernetes/overlays/production

# =============================================================================
# QUICK ACCESS
# =============================================================================

open-admin: ## Open Admin UI in browser
	@open http://localhost:$${ADMIN_UI_PORT:-5173} 2>/dev/null || \
	 xdg-open http://localhost:$${ADMIN_UI_PORT:-5173} 2>/dev/null || \
	 start http://localhost:$${ADMIN_UI_PORT:-5173} 2>/dev/null || \
	 echo "Open http://localhost:$${ADMIN_UI_PORT:-5173} in your browser"

open-grafana: ## Open Grafana in browser
	@open http://localhost:$${GRAFANA_PORT:-3030} 2>/dev/null || \
	 xdg-open http://localhost:$${GRAFANA_PORT:-3030} 2>/dev/null || \
	 start http://localhost:$${GRAFANA_PORT:-3030} 2>/dev/null || \
	 echo "Open http://localhost:$${GRAFANA_PORT:-3030} in your browser"

# =============================================================================
# VERSION INFO
# =============================================================================

version: ## Show version information
	@echo "$(CYAN)AI Gateway Platform$(RESET)"
	@echo "Docker: $$(docker --version)"
	@echo "Docker Compose: $$($(DOCKER_COMPOSE) version --short 2>/dev/null || $(DOCKER_COMPOSE) version)"
	@echo "Kubernetes: $$(kubectl version --client --short 2>/dev/null || echo 'not installed')"

# =============================================================================
# CLOUD DEPLOYMENT (GCP + Terraform)
# =============================================================================

# Environment selection (demo, staging, prod)
ENV ?= demo
TF_DIR := terraform/environments

# Main deployment targets
demo: ## Deploy demo environment to GCP
	@$(MAKE) _deploy ENV=demo

staging: ## Deploy staging environment to GCP
	@$(MAKE) _deploy ENV=staging

prod: ## Deploy production environment to GCP (requires confirmation)
	@echo "$(YELLOW)WARNING: Deploying to PRODUCTION!$(RESET)"
	@read -p "Type 'prod' to confirm: " confirm && [ "$$confirm" = "prod" ]
	@$(MAKE) _deploy ENV=prod

# Internal deployment workflow
_deploy: _infra _build _wait _seed
	@echo "$(GREEN)✓ $(ENV) environment deployed!$(RESET)"
	@$(MAKE) _output

_infra: ## Run Terraform to create/update infrastructure
	@echo "$(CYAN)Provisioning $(ENV) infrastructure...$(RESET)"
	cd $(TF_DIR) && terraform init -backend-config="prefix=$(ENV)" -reconfigure
	cd $(TF_DIR) && terraform apply -var-file=$(ENV).tfvars -auto-approve

_build: ## Build and push Docker images to Artifact Registry
	@echo "$(CYAN)Building and pushing Docker images...$(RESET)"
	@REPO=$$(cd $(TF_DIR) && terraform output -raw artifact_registry) && \
	REGION=$$(echo $$REPO | cut -d'-' -f1-2) && \
	PLATFORM_FLAG="" && \
	if [ "$$(uname -m)" = "arm64" ]; then \
		PLATFORM_FLAG="--platform linux/amd64"; \
		echo "Detected ARM64, building for linux/amd64..."; \
	fi && \
	gcloud auth configure-docker $$REGION-docker.pkg.dev --quiet && \
	echo "Building admin-api..." && \
	docker build $$PLATFORM_FLAG -t $$REPO/admin-api:latest ./src/admin-api && \
	docker push $$REPO/admin-api:latest && \
	echo "Building admin-ui..." && \
	docker build $$PLATFORM_FLAG -t $$REPO/admin-ui:latest ./ui/admin && \
	docker push $$REPO/admin-ui:latest && \
	echo "Building cost-predictor..." && \
	docker build $$PLATFORM_FLAG -t $$REPO/cost-predictor:latest ./src/cost-predictor && \
	docker push $$REPO/cost-predictor:latest && \
	echo "Building policy-router..." && \
	docker build $$PLATFORM_FLAG -t $$REPO/policy-router:latest ./src/policy-router && \
	docker push $$REPO/policy-router:latest && \
	echo "Building workflow-engine..." && \
	docker build $$PLATFORM_FLAG -t $$REPO/workflow-engine:latest ./src/workflow-engine && \
	docker push $$REPO/workflow-engine:latest && \
	echo "Building semantic-cache..." && \
	docker build $$PLATFORM_FLAG -t $$REPO/semantic-cache:latest ./src/semantic-cache && \
	docker push $$REPO/semantic-cache:latest && \
	echo "$(GREEN)✓ Images built and pushed$(RESET)"

_wait: ## Wait for services to be ready (after images are built)
	@echo "$(CYAN)Waiting for services to be ready...$(RESET)"
	@NAMESPACE=$$(cd $(TF_DIR) && terraform output -raw namespace) && \
	REPO=$$(cd $(TF_DIR) && terraform output -raw artifact_registry) && \
	echo "Updating custom service images..." && \
	kubectl -n $$NAMESPACE set image deployment/cost-predictor cost-predictor=$$REPO/cost-predictor:latest || true && \
	kubectl -n $$NAMESPACE set image deployment/policy-router policy-router=$$REPO/policy-router:latest || true && \
	kubectl -n $$NAMESPACE set image deployment/workflow-engine workflow-engine=$$REPO/workflow-engine:latest || true && \
	kubectl -n $$NAMESPACE set image deployment/semantic-cache semantic-cache=$$REPO/semantic-cache:latest || true && \
	echo "Restarting deployments to pick up new images..." && \
	kubectl -n $$NAMESPACE rollout restart deployment/admin-api deployment/admin-ui deployment/cost-predictor deployment/policy-router deployment/workflow-engine deployment/semantic-cache || true && \
	echo "Waiting for core pods..." && \
	kubectl -n $$NAMESPACE wait --for=condition=ready pod -l app=postgresql --timeout=300s && \
	kubectl -n $$NAMESPACE wait --for=condition=ready pod -l app=redis --timeout=300s && \
	kubectl -n $$NAMESPACE wait --for=condition=ready pod -l app=litellm --timeout=300s && \
	kubectl -n $$NAMESPACE wait --for=condition=ready pod -l app=admin-api --timeout=300s && \
	echo "$(GREEN)✓ All services ready$(RESET)"

_seed: ## Seed demo data (skipped for prod)
	@if [ "$(ENV)" != "prod" ]; then \
		echo "$(CYAN)Seeding $(ENV) data...$(RESET)"; \
		NAMESPACE=$$(cd $(TF_DIR) && terraform output -raw namespace) && \
		kubectl -n $$NAMESPACE port-forward svc/litellm 4000:4000 & \
		PF_PID=$$! && \
		sleep 10 && \
		GATEWAY_URL=http://localhost:4000 \
		LITELLM_MASTER_KEY=$$(cd $(TF_DIR) && terraform output -raw api_key) \
		./scripts/seed-demo-data.sh || true; \
		kill $$PF_PID 2>/dev/null || true; \
		echo "$(GREEN)✓ Demo data seeded$(RESET)"; \
	else \
		echo "$(YELLOW)Skipping seed for production$(RESET)"; \
	fi

_output: ## Show deployment outputs
	@cd $(TF_DIR) && terraform output

# Destroy targets
destroy: ## Destroy environment (ENV=demo|staging|prod)
	@echo "$(YELLOW)Destroying $(ENV) environment$(RESET)"
	@if [ "$(ENV)" = "prod" ]; then \
		read -p "Type 'destroy-prod' to confirm: " confirm && [ "$$confirm" = "destroy-prod" ]; \
	fi
	cd $(TF_DIR) && terraform init -backend-config="prefix=$(ENV)" -reconfigure
	cd $(TF_DIR) && terraform destroy -var-file=$(ENV).tfvars -auto-approve

demo-destroy: ## Destroy demo environment
	@$(MAKE) destroy ENV=demo

staging-destroy: ## Destroy staging environment
	@$(MAKE) destroy ENV=staging

prod-destroy: ## Destroy production environment (requires confirmation)
	@$(MAKE) destroy ENV=prod

# Cloud status/info
cloud-status: ## Show Terraform state for current environment
	cd $(TF_DIR) && terraform init -backend-config="prefix=$(ENV)" -reconfigure
	cd $(TF_DIR) && terraform show

cloud-output: ## Show Terraform outputs for current environment
	cd $(TF_DIR) && terraform output

cloud-plan: ## Show Terraform plan for current environment
	cd $(TF_DIR) && terraform init -backend-config="prefix=$(ENV)" -reconfigure
	cd $(TF_DIR) && terraform plan -var-file=$(ENV).tfvars
