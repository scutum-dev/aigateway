# AI Gateway - Fully Ephemeral Demo Environment
# Single command: terraform apply - creates infra, builds images, deploys services, sets up SSL, seeds data
# Single command: terraform destroy - tears everything down
#
# Cost: $0 when destroyed, ~$6-10/day when running

terraform {
  required_version = ">= 1.5"

  backend "gcs" {
    bucket = "aigateway-demo-tfstate"
    prefix = "demo-ephemeral"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.25"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }
}

# =============================================================================
# Variables
# =============================================================================

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "asia-south1"
}

variable "openai_api_key" {
  description = "OpenAI API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "anthropic_api_key" {
  description = "Anthropic API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "xai_api_key" {
  description = "xAI API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "google_api_key" {
  description = "Google AI API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "deepseek_api_key" {
  description = "DeepSeek API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "aws_access_key_id" {
  description = "AWS Access Key for Bedrock"
  type        = string
  sensitive   = true
  default     = ""
}

variable "aws_secret_access_key" {
  description = "AWS Secret Key for Bedrock"
  type        = string
  sensitive   = true
  default     = ""
}

variable "vertex_project" {
  description = "GCP Project for Vertex AI"
  type        = string
  default     = ""
}

variable "litellm_master_key" {
  description = "LiteLLM master key"
  type        = string
  sensitive   = true
  default     = "sk-litellm-demo-key"
}

variable "aws_region" {
  description = "AWS region for Route53 and Bedrock"
  type        = string
  default     = "ap-south-1"
}

variable "domain" {
  description = "Base domain (must exist in Route53)"
  type        = string
  default     = "deos.dev"
}

variable "subdomain" {
  description = "Subdomain for gateway"
  type        = string
  default     = "gateway"
}

variable "letsencrypt_email" {
  description = "Email for Let's Encrypt certificates"
  type        = string
  default     = "admin@deos.dev"
}

variable "grafana_password" {
  description = "Grafana admin password"
  type        = string
  sensitive   = true
  default     = "admin"
}

# =============================================================================
# Environment Sizing Variables (change these for prod vs demo)
# =============================================================================

variable "environment" {
  description = "Environment name (demo, staging, prod)"
  type        = string
  default     = "demo"
}

variable "replicas" {
  description = "Default replica count for services"
  type        = number
  default     = 1
}

variable "litellm_replicas" {
  description = "LiteLLM replica count"
  type        = number
  default     = 1
}

variable "min_replicas" {
  description = "HPA min replicas"
  type        = number
  default     = 1
}

variable "max_replicas" {
  description = "HPA max replicas"
  type        = number
  default     = 3
}

variable "deletion_protection" {
  description = "Enable deletion protection (true for prod)"
  type        = bool
  default     = false
}

# =============================================================================
# Providers
# =============================================================================

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "aws" {
  region = var.aws_region
}

# Get GCP auth token
data "google_client_config" "default" {}

# Kubernetes provider - uses gcloud credentials after cluster creation
provider "kubernetes" {
  host                   = "https://${google_container_cluster.main.endpoint}"
  token                  = data.google_client_config.default.access_token
  cluster_ca_certificate = base64decode(google_container_cluster.main.master_auth[0].cluster_ca_certificate)
}

provider "helm" {
  kubernetes {
    host                   = "https://${google_container_cluster.main.endpoint}"
    token                  = data.google_client_config.default.access_token
    cluster_ca_certificate = base64decode(google_container_cluster.main.master_auth[0].cluster_ca_certificate)
  }
}

# =============================================================================
# Artifact Registry (for Docker images)
# =============================================================================

resource "google_artifact_registry_repository" "main" {
  location      = var.region
  repository_id = "gateway-images"
  description   = "Docker images for AI Gateway"
  format        = "DOCKER"
  project       = var.project_id
}

# =============================================================================
# VPC
# =============================================================================

resource "google_compute_network" "main" {
  name                    = "gateway-demo-ephemeral"
  project                 = var.project_id
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "main" {
  name          = "gateway-demo-subnet"
  project       = var.project_id
  region        = var.region
  network       = google_compute_network.main.id
  ip_cidr_range = "10.0.0.0/20"

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.1.0.0/16"
  }

  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "10.2.0.0/20"
  }
}

# =============================================================================
# GKE Autopilot
# =============================================================================

resource "google_container_cluster" "main" {
  name     = "gateway-demo"
  location = var.region
  project  = var.project_id

  enable_autopilot = true

  network    = google_compute_network.main.name
  subnetwork = google_compute_subnetwork.main.name

  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = "172.16.0.0/28"
  }

  master_authorized_networks_config {
    cidr_blocks {
      cidr_block   = "0.0.0.0/0"
      display_name = "All"
    }
  }

  release_channel {
    channel = "REGULAR"
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  deletion_protection = var.deletion_protection
}

# =============================================================================
# Build Docker Images using Cloud Build
# =============================================================================

resource "null_resource" "build_images" {
  depends_on = [google_artifact_registry_repository.main, google_container_cluster.main]

  provisioner "local-exec" {
    working_dir = "${path.module}/../../../"
    command     = <<-EOT
      REPO="${var.region}-docker.pkg.dev/${var.project_id}/gateway-images"

      # Configure docker to use gcloud credentials
      gcloud auth configure-docker ${var.region}-docker.pkg.dev --quiet

      echo "Building admin-api..."
      docker build -t $REPO/admin-api:latest ./src/admin-api
      docker push $REPO/admin-api:latest

      echo "Building admin-ui..."
      docker build -t $REPO/admin-ui:latest ./ui/admin
      docker push $REPO/admin-ui:latest

      echo "Images built and pushed successfully"
    EOT
  }

  triggers = {
    # Rebuild when Dockerfiles change
    admin_api_hash = filemd5("${path.module}/../../../src/admin-api/Dockerfile")
    admin_ui_hash  = filemd5("${path.module}/../../../ui/admin/Dockerfile")
    cluster_id     = google_container_cluster.main.id
  }
}

# =============================================================================
# Kubernetes Namespace
# =============================================================================

resource "kubernetes_namespace" "gateway" {
  depends_on = [google_container_cluster.main]

  metadata {
    name = "gateway-demo"
  }
}

# =============================================================================
# Secrets
# =============================================================================

resource "kubernetes_secret" "gateway_secrets" {
  depends_on = [kubernetes_namespace.gateway]

  metadata {
    name      = "gateway-secrets"
    namespace = "gateway-demo"
  }

  data = {
    DATABASE_URL          = "postgresql://litellm:litellm@postgresql:5432/litellm"
    REDIS_URL             = "redis://redis:6379"
    LITELLM_MASTER_KEY    = var.litellm_master_key
    OPENAI_API_KEY        = var.openai_api_key
    ANTHROPIC_API_KEY     = var.anthropic_api_key
    XAI_API_KEY           = var.xai_api_key
    GOOGLE_API_KEY        = var.google_api_key
    DEEPSEEK_API_KEY      = var.deepseek_api_key
    AWS_ACCESS_KEY_ID     = var.aws_access_key_id
    AWS_SECRET_ACCESS_KEY = var.aws_secret_access_key
    AWS_REGION_NAME       = var.aws_region
    VERTEX_PROJECT        = var.vertex_project != "" ? var.vertex_project : var.project_id
    JWT_SECRET_KEY        = "jwt-secret-${var.project_id}"
    GRAFANA_PASSWORD      = var.grafana_password
  }
}

# =============================================================================
# Deploy Kubernetes Manifests
# =============================================================================

resource "null_resource" "get_credentials" {
  depends_on = [google_container_cluster.main]

  provisioner "local-exec" {
    command = "gcloud container clusters get-credentials ${google_container_cluster.main.name} --region ${var.region} --project ${var.project_id}"
  }

  triggers = {
    cluster_id = google_container_cluster.main.id
  }
}

# Deploy base services from kustomize
resource "null_resource" "deploy_services" {
  depends_on = [
    null_resource.get_credentials,
    kubernetes_secret.gateway_secrets,
    null_resource.build_images
  ]

  provisioner "local-exec" {
    working_dir = "${path.module}/../../../"
    command     = "kubectl apply -k kubernetes/overlays/demo-ephemeral"
  }

  triggers = {
    cluster_id = google_container_cluster.main.id
  }
}

# =============================================================================
# Nginx Ingress Controller
# =============================================================================

resource "helm_release" "nginx_ingress" {
  depends_on = [google_container_cluster.main]

  name             = "ingress-nginx"
  repository       = "https://kubernetes.github.io/ingress-nginx"
  chart            = "ingress-nginx"
  namespace        = "ingress-nginx"
  create_namespace = true
  version          = "4.9.1"

  set {
    name  = "controller.service.type"
    value = "LoadBalancer"
  }

  set {
    name  = "controller.config.proxy-body-size"
    value = "50m"
  }

  set {
    name  = "controller.config.proxy-read-timeout"
    value = "600"
  }

  set {
    name  = "controller.config.proxy-send-timeout"
    value = "600"
  }

  wait = true
}

# =============================================================================
# Cert-Manager for TLS
# =============================================================================

resource "helm_release" "cert_manager" {
  depends_on = [google_container_cluster.main]

  name             = "cert-manager"
  repository       = "https://charts.jetstack.io"
  chart            = "cert-manager"
  namespace        = "cert-manager"
  create_namespace = true
  version          = "v1.14.4"

  set {
    name  = "installCRDs"
    value = "true"
  }

  set {
    name  = "global.leaderElection.namespace"
    value = "cert-manager"
  }

  wait = true
}

# ClusterIssuer for Let's Encrypt
resource "null_resource" "cluster_issuer" {
  depends_on = [helm_release.cert_manager]

  provisioner "local-exec" {
    command = <<-EOT
      kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: ${var.letsencrypt_email}
    privateKeySecretRef:
      name: letsencrypt-prod-key
    solvers:
      - http01:
          ingress:
            class: nginx
EOF
    EOT
  }

  triggers = {
    cluster_id = google_container_cluster.main.id
  }
}

# =============================================================================
# Ingress with TLS
# =============================================================================

resource "kubernetes_ingress_v1" "gateway" {
  depends_on = [
    null_resource.deploy_services,
    helm_release.nginx_ingress,
    null_resource.cluster_issuer
  ]

  metadata {
    name      = "gateway-ingress"
    namespace = "gateway-demo"
    annotations = {
      "cert-manager.io/cluster-issuer"                 = "letsencrypt-prod"
      "nginx.ingress.kubernetes.io/proxy-body-size"    = "50m"
      "nginx.ingress.kubernetes.io/proxy-read-timeout" = "600"
      "nginx.ingress.kubernetes.io/proxy-send-timeout" = "600"
    }
  }

  spec {
    ingress_class_name = "nginx"

    tls {
      hosts       = ["${var.subdomain}.${var.domain}"]
      secret_name = "gateway-tls"
    }

    rule {
      host = "${var.subdomain}.${var.domain}"
      http {
        path {
          path      = "/"
          path_type = "Prefix"
          backend {
            service {
              name = "litellm"
              port {
                number = 4000
              }
            }
          }
        }
      }
    }
  }
}

# =============================================================================
# Update Admin API/UI Deployments with Real Images
# =============================================================================

resource "null_resource" "patch_deployments" {
  depends_on = [
    null_resource.deploy_services,
    null_resource.build_images
  ]

  provisioner "local-exec" {
    command = <<-EOT
      REPO="${var.region}-docker.pkg.dev/${var.project_id}/gateway-images"

      # Patch admin-api to use real image
      kubectl -n gateway-demo patch deployment admin-api --type='json' -p='[
        {"op": "replace", "path": "/spec/template/spec/containers/0/image", "value": "'$REPO'/admin-api:latest"},
        {"op": "replace", "path": "/spec/template/spec/containers/0/command", "value": null},
        {"op": "replace", "path": "/spec/template/spec/containers/0/args", "value": null}
      ]' || true

      # Patch admin-ui to use real image
      kubectl -n gateway-demo patch deployment admin-ui --type='json' -p='[
        {"op": "replace", "path": "/spec/template/spec/containers/0/image", "value": "'$REPO'/admin-ui:latest"}
      ]' || true

      # Scale LiteLLM based on environment
      kubectl -n gateway-demo scale deployment litellm --replicas=${var.litellm_replicas}

      # Update HPA min/max replicas
      kubectl -n gateway-demo patch hpa litellm --type='json' -p='[
        {"op": "replace", "path": "/spec/minReplicas", "value": ${var.min_replicas}},
        {"op": "replace", "path": "/spec/maxReplicas", "value": ${var.max_replicas}}
      ]' || true

      echo "Deployments patched: images updated, replicas=${var.litellm_replicas}, HPA=${var.min_replicas}-${var.max_replicas}"
    EOT
  }

  triggers = {
    cluster_id       = google_container_cluster.main.id
    image_hash       = null_resource.build_images.id
    replicas         = var.litellm_replicas
    min_replicas     = var.min_replicas
    max_replicas     = var.max_replicas
  }
}

# =============================================================================
# Wait for Services
# =============================================================================

resource "null_resource" "wait_for_services" {
  depends_on = [
    null_resource.deploy_services,
    null_resource.patch_deployments
  ]

  provisioner "local-exec" {
    command = <<-EOT
      echo "Waiting for pods to be ready..."
      kubectl -n gateway-demo wait --for=condition=ready pod -l app=postgresql --timeout=300s || true
      kubectl -n gateway-demo wait --for=condition=ready pod -l app=redis --timeout=300s || true
      kubectl -n gateway-demo wait --for=condition=ready pod -l app=litellm --timeout=300s || true
      kubectl -n gateway-demo wait --for=condition=ready pod -l app=admin-api --timeout=300s || true
      echo "Core services ready"
    EOT
  }

  triggers = {
    cluster_id = google_container_cluster.main.id
  }
}

# =============================================================================
# Seed Demo Data
# =============================================================================

resource "null_resource" "seed_demo_data" {
  depends_on = [null_resource.wait_for_services]

  provisioner "local-exec" {
    working_dir = "${path.module}/../../../"
    command     = <<-EOT
      # Start port-forward in background
      kubectl -n gateway-demo port-forward svc/litellm 4000:4000 &
      PF_PID=$!
      sleep 10

      # Run seed script
      GATEWAY_URL=http://localhost:4000 \
      LITELLM_MASTER_KEY=${var.litellm_master_key} \
      ./scripts/seed-demo-data.sh || true

      # Kill port-forward
      kill $PF_PID 2>/dev/null || true
    EOT
  }

  triggers = {
    cluster_id = google_container_cluster.main.id
  }
}

# =============================================================================
# AWS Route53 DNS
# =============================================================================

data "aws_route53_zone" "main" {
  name = "${var.domain}."
}

# Wait for LoadBalancer IP and update Route53
resource "null_resource" "update_route53" {
  depends_on = [helm_release.nginx_ingress]

  provisioner "local-exec" {
    command = <<-EOT
      echo "Waiting for Ingress LoadBalancer IP..."
      for i in {1..60}; do
        LB_IP=$(kubectl -n ingress-nginx get svc ingress-nginx-controller -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null)
        if [ -n "$LB_IP" ] && [ "$LB_IP" != "null" ]; then
          echo "Got LoadBalancer IP: $LB_IP"

          # Update Route53 A record
          aws route53 change-resource-record-sets \
            --hosted-zone-id ${data.aws_route53_zone.main.zone_id} \
            --change-batch '{
              "Changes": [
                {
                  "Action": "UPSERT",
                  "ResourceRecordSet": {
                    "Name": "${var.subdomain}.${var.domain}",
                    "Type": "A",
                    "TTL": 60,
                    "ResourceRecords": [{"Value": "'$LB_IP'"}]
                  }
                }
              ]
            }'

          echo "Route53 updated: ${var.subdomain}.${var.domain} -> $LB_IP"
          exit 0
        fi
        echo "Waiting for IP... ($i/60)"
        sleep 5
      done
      echo "ERROR: Timed out waiting for LoadBalancer IP"
      exit 1
    EOT
  }

  triggers = {
    cluster_id = google_container_cluster.main.id
  }
}

# =============================================================================
# Outputs
# =============================================================================

output "cluster_name" {
  value = google_container_cluster.main.name
}

output "cluster_endpoint" {
  value     = google_container_cluster.main.endpoint
  sensitive = true
}

output "artifact_registry" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/gateway-images"
}

output "gateway_url" {
  value = "https://${var.subdomain}.${var.domain}"
}

output "ingress_ip" {
  description = "Run: kubectl -n ingress-nginx get svc ingress-nginx-controller -o jsonpath='{.status.loadBalancer.ingress[0].ip}'"
  value       = "Check with kubectl after apply"
}

output "api_key" {
  value     = var.litellm_master_key
  sensitive = true
}

output "credentials" {
  sensitive = true
  value = {
    gateway_api_key  = var.litellm_master_key
    grafana_user     = "admin"
    grafana_password = var.grafana_password
    admin_ui_api_key = var.litellm_master_key
  }
}

output "urls" {
  value = {
    gateway  = "https://${var.subdomain}.${var.domain}"
    api_docs = "https://${var.subdomain}.${var.domain}/docs"
    health   = "https://${var.subdomain}.${var.domain}/health/readiness"
  }
}

output "environment_config" {
  value = {
    environment         = var.environment
    replicas            = var.litellm_replicas
    hpa_min             = var.min_replicas
    hpa_max             = var.max_replicas
    deletion_protection = var.deletion_protection
  }
}

output "access_commands" {
  sensitive = true
  value     = <<-EOT

    === AI Gateway ${upper(var.environment)} Environment Ready ===

    Gateway URL: https://${var.subdomain}.${var.domain}
    API Key: ${var.litellm_master_key}
    Environment: ${var.environment}
    Replicas: ${var.litellm_replicas} (HPA: ${var.min_replicas}-${var.max_replicas})

    Connect to cluster:
      gcloud container clusters get-credentials gateway-demo --region ${var.region} --project ${var.project_id}

    Test API:
      curl https://${var.subdomain}.${var.domain}/health/readiness
      curl https://${var.subdomain}.${var.domain}/v1/models -H "Authorization: Bearer ${var.litellm_master_key}"

    Access Grafana (port-forward):
      kubectl -n gateway-demo port-forward svc/grafana 3000:3000
      Open http://localhost:3000 (admin/${var.grafana_password})

    Access Admin API (port-forward):
      kubectl -n gateway-demo port-forward svc/admin-api 8086:8086
      curl -X POST http://localhost:8086/auth/login \
        -H "Content-Type: application/json" \
        -d '{"api_key": "${var.litellm_master_key}"}'

    ${var.deletion_protection ? "WARNING: Deletion protection ENABLED - terraform destroy will fail" : "Destroy when done: terraform destroy"}

  EOT
}
