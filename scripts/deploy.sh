#!/bin/bash
# Deploy script with environment selection
#
# Usage:
#   ./scripts/deploy.sh dev      # Deploy development environment
#   ./scripts/deploy.sh staging  # Deploy staging environment
#   ./scripts/deploy.sh prod     # Deploy production environment
#
# Options:
#   --build    Force rebuild images
#   --detach   Run in background
#   --down     Stop services instead of starting

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Parse arguments
ENVIRONMENT=""
BUILD_FLAG=""
DETACH_FLAG="-d"
ACTION="up"

while [[ $# -gt 0 ]]; do
  case $1 in
    dev|development)
      ENVIRONMENT="dev"
      shift
      ;;
    staging|stg)
      ENVIRONMENT="staging"
      shift
      ;;
    prod|production)
      ENVIRONMENT="production"
      shift
      ;;
    --build)
      BUILD_FLAG="--build"
      shift
      ;;
    --no-detach|--foreground)
      DETACH_FLAG=""
      shift
      ;;
    --down|down)
      ACTION="down"
      shift
      ;;
    --restart)
      ACTION="restart"
      shift
      ;;
    --logs)
      ACTION="logs"
      shift
      ;;
    --help|-h)
      echo "Usage: $0 <environment> [options]"
      echo ""
      echo "Environments:"
      echo "  dev, development   Deploy development environment"
      echo "  staging, stg       Deploy staging environment"
      echo "  prod, production   Deploy production environment"
      echo ""
      echo "Options:"
      echo "  --build           Force rebuild images"
      echo "  --no-detach       Run in foreground (show logs)"
      echo "  --down            Stop services"
      echo "  --restart         Restart services"
      echo "  --logs            Show service logs"
      echo "  --help            Show this help message"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Default to dev if no environment specified
if [ -z "$ENVIRONMENT" ]; then
  ENVIRONMENT="dev"
  echo "No environment specified, defaulting to: $ENVIRONMENT"
fi

# Set compose files based on environment
COMPOSE_FILES="-f ${PROJECT_DIR}/docker-compose.yaml"

case "$ENVIRONMENT" in
  dev)
    COMPOSE_FILES="$COMPOSE_FILES -f ${PROJECT_DIR}/docker-compose.override.dev.yaml"
    ENV_FILE="${PROJECT_DIR}/config/feature-flags/dev.yaml"
    ;;
  staging)
    COMPOSE_FILES="$COMPOSE_FILES -f ${PROJECT_DIR}/docker-compose.override.staging.yaml"
    ENV_FILE="${PROJECT_DIR}/config/feature-flags/staging.yaml"
    ;;
  production)
    COMPOSE_FILES="$COMPOSE_FILES -f ${PROJECT_DIR}/docker-compose.override.production.yaml"
    ENV_FILE="${PROJECT_DIR}/config/feature-flags/production.yaml"
    echo ""
    echo "WARNING: You are deploying to PRODUCTION"
    echo "For production deployments, consider using Kubernetes instead."
    echo ""
    read -p "Are you sure you want to continue? (yes/no) " -r
    if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
      echo "Deployment cancelled."
      exit 1
    fi
    ;;
esac

echo "=== AI Gateway Deployment ==="
echo "Environment: $ENVIRONMENT"
echo "Config file: $ENV_FILE"
echo ""

# Export environment variable
export ENVIRONMENT

cd "$PROJECT_DIR"

case "$ACTION" in
  up)
    echo "Starting services..."
    docker compose $COMPOSE_FILES up $BUILD_FLAG $DETACH_FLAG

    if [ -n "$DETACH_FLAG" ]; then
      echo ""
      echo "Services started in background."
      echo ""
      echo "Useful commands:"
      echo "  View logs:    docker compose $COMPOSE_FILES logs -f"
      echo "  Stop:         ./scripts/deploy.sh $ENVIRONMENT --down"
      echo "  Status:       docker compose $COMPOSE_FILES ps"
      echo ""
      echo "Initialize Vault:"
      echo "  ENVIRONMENT=$ENVIRONMENT ./scripts/vault-init.sh"
    fi
    ;;

  down)
    echo "Stopping services..."
    docker compose $COMPOSE_FILES down
    echo "Services stopped."
    ;;

  restart)
    echo "Restarting services..."
    docker compose $COMPOSE_FILES restart
    echo "Services restarted."
    ;;

  logs)
    docker compose $COMPOSE_FILES logs -f
    ;;
esac
