# AI Gateway - Multi-Environment Terraform Configuration
#
# Usage:
#   make demo      - Deploy demo environment
#   make staging   - Deploy staging environment
#   make prod      - Deploy production (with confirmation)
#   make destroy ENV=demo - Destroy any environment
#
# Or manually:
#   terraform init -backend-config="prefix=demo"
#   terraform apply -var-file=demo.tfvars

# =============================================================================
# Providers
# =============================================================================

provider "google" {
  project               = var.project_id
  region                = var.region
  user_project_override = true
  billing_project       = var.project_id
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
# GCP Budget Alert
# =============================================================================

data "google_project" "current" {
  project_id = var.project_id
}

data "google_billing_account" "account" {
  billing_account = var.billing_account
}

resource "google_billing_budget" "monthly" {
  billing_account = data.google_billing_account.account.id
  display_name    = "AI Gateway ${var.environment} Budget"

  budget_filter {
    projects = ["projects/${data.google_project.current.number}"]
  }

  amount {
    specified_amount {
      currency_code = "INR"
      units         = "2000"
    }
  }

  threshold_rules {
    threshold_percent = 0.5
  }

  threshold_rules {
    threshold_percent = 0.8
  }

  threshold_rules {
    threshold_percent = 1.0
  }
}

# =============================================================================
# Locals
# =============================================================================

locals {
  cluster_name   = "gateway-${var.environment}"
  namespace      = "gateway-${var.environment}"
  network_name   = "gateway-${var.environment}"
  full_domain    = "${var.subdomain}.${var.domain}"
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
  name                    = local.network_name
  project                 = var.project_id
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "main" {
  name          = "${local.network_name}-subnet"
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
# Cloud NAT (required for private nodes to pull public images)
# =============================================================================

resource "google_compute_router" "main" {
  name    = "${local.network_name}-router"
  project = var.project_id
  region  = var.region
  network = google_compute_network.main.id
}

resource "google_compute_router_nat" "main" {
  name                               = "${local.network_name}-nat"
  project                            = var.project_id
  router                             = google_compute_router.main.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = false
    filter = "ERRORS_ONLY"
  }
}

# =============================================================================
# GKE Autopilot
# =============================================================================

resource "google_container_cluster" "main" {
  name     = local.cluster_name
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
# Kubernetes Namespace
# =============================================================================

resource "kubernetes_namespace" "gateway" {
  depends_on = [google_container_cluster.main]

  metadata {
    name = local.namespace
  }
}

# =============================================================================
# Secrets
# =============================================================================

resource "kubernetes_secret" "gateway_secrets" {
  depends_on = [kubernetes_namespace.gateway]

  metadata {
    name      = "gateway-secrets"
    namespace = local.namespace
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
    kubernetes_secret.gateway_secrets
  ]

  provisioner "local-exec" {
    working_dir = "${path.module}/../../"
    command     = "kubectl apply -k kubernetes/overlays/${var.kustomize_overlay}"
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
  timeout          = 600  # 10 min - GKE Autopilot needs time to provision nodes

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
  timeout          = 600  # 10 min - GKE Autopilot needs time to provision nodes

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
    namespace = local.namespace
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
      hosts       = [local.full_domain]
      secret_name = "gateway-tls"
    }

    rule {
      host = local.full_domain
      http {
        # LiteLLM API routes (must be before /)
        path {
          path      = "/v1"
          path_type = "Prefix"
          backend {
            service {
              name = "litellm"
              port { number = 4000 }
            }
          }
        }

        path {
          path      = "/docs"
          path_type = "Prefix"
          backend {
            service {
              name = "litellm"
              port { number = 4000 }
            }
          }
        }

        path {
          path      = "/openapi.json"
          path_type = "Exact"
          backend {
            service {
              name = "litellm"
              port { number = 4000 }
            }
          }
        }

        path {
          path      = "/health"
          path_type = "Prefix"
          backend {
            service {
              name = "litellm"
              port { number = 4000 }
            }
          }
        }

        path {
          path      = "/key"
          path_type = "Prefix"
          backend {
            service {
              name = "litellm"
              port { number = 4000 }
            }
          }
        }

        path {
          path      = "/model"
          path_type = "Prefix"
          backend {
            service {
              name = "litellm"
              port { number = 4000 }
            }
          }
        }

        path {
          path      = "/spend"
          path_type = "Prefix"
          backend {
            service {
              name = "litellm"
              port { number = 4000 }
            }
          }
        }

        # Admin API routes
        path {
          path      = "/api"
          path_type = "Prefix"
          backend {
            service {
              name = "admin-api"
              port { number = 8086 }
            }
          }
        }

        path {
          path      = "/auth"
          path_type = "Prefix"
          backend {
            service {
              name = "admin-api"
              port { number = 8086 }
            }
          }
        }

        # Landing page - default route
        path {
          path      = "/"
          path_type = "Prefix"
          backend {
            service {
              name = "landing-ui"
              port { number = 9999 }
            }
          }
        }
      }
    }
  }
}

# Admin UI Ingress (with path rewrite)
resource "kubernetes_ingress_v1" "admin_ui" {
  depends_on = [
    null_resource.deploy_services,
    helm_release.nginx_ingress,
    null_resource.cluster_issuer
  ]

  metadata {
    name      = "admin-ui-ingress"
    namespace = local.namespace
    annotations = {
      "cert-manager.io/cluster-issuer"                    = "letsencrypt-prod"
      "nginx.ingress.kubernetes.io/rewrite-target"        = "/$2"
      "nginx.ingress.kubernetes.io/use-regex"             = "true"
    }
  }

  spec {
    ingress_class_name = "nginx"

    tls {
      hosts       = [local.full_domain]
      secret_name = "gateway-tls"
    }

    rule {
      host = local.full_domain
      http {
        path {
          path      = "/admin(/|$)(.*)"
          path_type = "ImplementationSpecific"
          backend {
            service {
              name = "admin-ui"
              port {
                number = 5173
              }
            }
          }
        }
      }
    }
  }
}

# Admin API Ingress (with path rewrite)
resource "kubernetes_ingress_v1" "admin_api" {
  depends_on = [
    null_resource.deploy_services,
    helm_release.nginx_ingress,
    null_resource.cluster_issuer
  ]

  metadata {
    name      = "admin-api-ingress"
    namespace = local.namespace
    annotations = {
      "cert-manager.io/cluster-issuer"                    = "letsencrypt-prod"
      "nginx.ingress.kubernetes.io/rewrite-target"        = "/$2"
      "nginx.ingress.kubernetes.io/use-regex"             = "true"
    }
  }

  spec {
    ingress_class_name = "nginx"

    tls {
      hosts       = [local.full_domain]
      secret_name = "gateway-tls"
    }

    rule {
      host = local.full_domain
      http {
        path {
          path      = "/admin-api(/|$)(.*)"
          path_type = "ImplementationSpecific"
          backend {
            service {
              name = "admin-api"
              port {
                number = 8086
              }
            }
          }
        }
      }
    }
  }
}

# Grafana Ingress (Grafana handles subpath with GF_SERVER_SERVE_FROM_SUB_PATH)
resource "kubernetes_ingress_v1" "grafana" {
  depends_on = [
    null_resource.deploy_services,
    helm_release.nginx_ingress,
    null_resource.cluster_issuer
  ]

  metadata {
    name      = "grafana-ingress"
    namespace = local.namespace
    annotations = {
      "cert-manager.io/cluster-issuer"              = "letsencrypt-prod"
      "nginx.ingress.kubernetes.io/proxy-body-size" = "50m"
    }
  }

  spec {
    ingress_class_name = "nginx"

    tls {
      hosts       = [local.full_domain]
      secret_name = "gateway-tls"
    }

    rule {
      host = local.full_domain
      http {
        path {
          path      = "/grafana"
          path_type = "Prefix"
          backend {
            service {
              name = "grafana"
              port {
                number = 3000
              }
            }
          }
        }
      }
    }
  }
}

# Cost Predictor Ingress
resource "kubernetes_ingress_v1" "cost_predictor" {
  depends_on = [
    null_resource.deploy_services,
    helm_release.nginx_ingress,
    null_resource.cluster_issuer
  ]

  metadata {
    name      = "cost-predictor-ingress"
    namespace = local.namespace
    annotations = {
      "cert-manager.io/cluster-issuer"                    = "letsencrypt-prod"
      "nginx.ingress.kubernetes.io/rewrite-target"        = "/$2"
      "nginx.ingress.kubernetes.io/use-regex"             = "true"
    }
  }

  spec {
    ingress_class_name = "nginx"

    tls {
      hosts       = [local.full_domain]
      secret_name = "gateway-tls"
    }

    rule {
      host = local.full_domain
      http {
        path {
          path      = "/cost-predictor(/|$)(.*)"
          path_type = "ImplementationSpecific"
          backend {
            service {
              name = "cost-predictor"
              port {
                number = 8080
              }
            }
          }
        }
      }
    }
  }
}

# Policy Router Ingress (Cedar policy-based routing)
resource "kubernetes_ingress_v1" "policy_router" {
  depends_on = [
    null_resource.deploy_services,
    helm_release.nginx_ingress,
    null_resource.cluster_issuer
  ]

  metadata {
    name      = "policy-router-ingress"
    namespace = local.namespace
    annotations = {
      "cert-manager.io/cluster-issuer"                    = "letsencrypt-prod"
      "nginx.ingress.kubernetes.io/rewrite-target"        = "/$2"
      "nginx.ingress.kubernetes.io/use-regex"             = "true"
    }
  }

  spec {
    ingress_class_name = "nginx"
    tls {
      hosts       = [local.full_domain]
      secret_name = "gateway-tls"
    }
    rule {
      host = local.full_domain
      http {
        path {
          path      = "/policy-router(/|$)(.*)"
          path_type = "ImplementationSpecific"
          backend {
            service {
              name = "policy-router"
              port { number = 8084 }
            }
          }
        }
      }
    }
  }
}

# Workflow Engine Ingress (LangGraph workflows)
resource "kubernetes_ingress_v1" "workflow_engine" {
  depends_on = [
    null_resource.deploy_services,
    helm_release.nginx_ingress,
    null_resource.cluster_issuer
  ]

  metadata {
    name      = "workflow-engine-ingress"
    namespace = local.namespace
    annotations = {
      "cert-manager.io/cluster-issuer"                    = "letsencrypt-prod"
      "nginx.ingress.kubernetes.io/rewrite-target"        = "/$2"
      "nginx.ingress.kubernetes.io/use-regex"             = "true"
    }
  }

  spec {
    ingress_class_name = "nginx"
    tls {
      hosts       = [local.full_domain]
      secret_name = "gateway-tls"
    }
    rule {
      host = local.full_domain
      http {
        path {
          path      = "/workflows(/|$)(.*)"
          path_type = "ImplementationSpecific"
          backend {
            service {
              name = "workflow-engine"
              port { number = 8085 }
            }
          }
        }
      }
    }
  }
}

# Agent Gateway Ingress (MCP + A2A protocols)
resource "kubernetes_ingress_v1" "agentgateway" {
  depends_on = [
    null_resource.deploy_services,
    helm_release.nginx_ingress,
    null_resource.cluster_issuer
  ]

  metadata {
    name      = "agentgateway-ingress"
    namespace = local.namespace
    annotations = {
      "cert-manager.io/cluster-issuer"                    = "letsencrypt-prod"
      "nginx.ingress.kubernetes.io/rewrite-target"        = "/$2"
      "nginx.ingress.kubernetes.io/use-regex"             = "true"
    }
  }

  spec {
    ingress_class_name = "nginx"
    tls {
      hosts       = [local.full_domain]
      secret_name = "gateway-tls"
    }
    rule {
      host = local.full_domain
      http {
        path {
          path      = "/mcp(/|$)(.*)"
          path_type = "ImplementationSpecific"
          backend {
            service {
              name = "agentgateway"
              port { number = 9000 }
            }
          }
        }
      }
    }
  }
}

# Semantic Cache Ingress
resource "kubernetes_ingress_v1" "semantic_cache" {
  depends_on = [
    null_resource.deploy_services,
    helm_release.nginx_ingress,
    null_resource.cluster_issuer
  ]

  metadata {
    name      = "semantic-cache-ingress"
    namespace = local.namespace
    annotations = {
      "cert-manager.io/cluster-issuer"                    = "letsencrypt-prod"
      "nginx.ingress.kubernetes.io/rewrite-target"        = "/$2"
      "nginx.ingress.kubernetes.io/use-regex"             = "true"
    }
  }

  spec {
    ingress_class_name = "nginx"
    tls {
      hosts       = [local.full_domain]
      secret_name = "gateway-tls"
    }
    rule {
      host = local.full_domain
      http {
        path {
          path      = "/semantic-cache(/|$)(.*)"
          path_type = "ImplementationSpecific"
          backend {
            service {
              name = "semantic-cache"
              port { number = 8083 }
            }
          }
        }
      }
    }
  }
}

# =============================================================================
# Patch Deployments with Images and Scaling
# =============================================================================

resource "null_resource" "patch_deployments" {
  depends_on = [null_resource.deploy_services]

  provisioner "local-exec" {
    command = <<-EOT
      REPO="${var.region}-docker.pkg.dev/${var.project_id}/gateway-images"

      # Patch admin-api to use real image
      kubectl -n ${local.namespace} patch deployment admin-api --type='json' -p='[
        {"op": "replace", "path": "/spec/template/spec/containers/0/image", "value": "'$REPO'/admin-api:latest"},
        {"op": "replace", "path": "/spec/template/spec/containers/0/command", "value": null},
        {"op": "replace", "path": "/spec/template/spec/containers/0/args", "value": null}
      ]' || true

      # Patch admin-ui to use real image
      kubectl -n ${local.namespace} patch deployment admin-ui --type='json' -p='[
        {"op": "replace", "path": "/spec/template/spec/containers/0/image", "value": "'$REPO'/admin-ui:latest"}
      ]' || true

      # Scale LiteLLM based on environment
      kubectl -n ${local.namespace} scale deployment litellm --replicas=${var.litellm_replicas}

      # Update HPA min/max replicas
      kubectl -n ${local.namespace} patch hpa litellm --type='json' -p='[
        {"op": "replace", "path": "/spec/minReplicas", "value": ${var.min_replicas}},
        {"op": "replace", "path": "/spec/maxReplicas", "value": ${var.max_replicas}}
      ]' || true

      # Configure Grafana for subpath serving and password
      kubectl -n ${local.namespace} set env deployment/grafana \
        GF_SERVER_ROOT_URL=https://${local.full_domain}/grafana \
        GF_SERVER_SERVE_FROM_SUB_PATH=true \
        GF_SECURITY_ADMIN_PASSWORD="${var.grafana_password}" \
        GF_SECURITY_DISABLE_INITIAL_ADMIN_CREATION=false \
        GF_AUTH_DISABLE_LOGIN_FORM=false || true

      # Force update configmaps and deployments, then apply kustomize
      kubectl -n ${local.namespace} delete configmap litellm-config --ignore-not-found=true
      kubectl -n ${local.namespace} delete deployment litellm --ignore-not-found=true
      kubectl kustomize ${path.module}/../../kubernetes/overlays/${var.kustomize_overlay} | kubectl apply -f -

      # Configure LiteLLM for Swagger docs to use correct base URL
      kubectl -n ${local.namespace} set env deployment/litellm \
        PROXY_BASE_URL=https://${local.full_domain} || true

      # Restart LiteLLM to pick up config changes
      kubectl -n ${local.namespace} rollout restart deployment/litellm || true

      echo "Deployments patched: images updated, replicas=${var.litellm_replicas}, HPA=${var.min_replicas}-${var.max_replicas}"
    EOT
  }

  triggers = {
    cluster_id       = google_container_cluster.main.id
    replicas         = var.litellm_replicas
    min_replicas     = var.min_replicas
    max_replicas     = var.max_replicas
    full_domain      = local.full_domain
    litellm_config   = filemd5("${path.module}/../../kubernetes/base/litellm/configmap.yaml")
    litellm_deploy   = filemd5("${path.module}/../../kubernetes/base/litellm/deployment.yaml")
  }
}

# =============================================================================
# Note: Service readiness is handled by Makefile after image build
# Terraform only provisions infrastructure; Makefile orchestrates the full deploy
# =============================================================================

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
                    "Name": "${local.full_domain}",
                    "Type": "A",
                    "TTL": 60,
                    "ResourceRecords": [{"Value": "'$LB_IP'"}]
                  }
                }
              ]
            }'

          echo "Route53 updated: ${local.full_domain} -> $LB_IP"
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
