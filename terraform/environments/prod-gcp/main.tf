# AI Gateway Platform - GCP Production Environment (Mumbai)
# Terraform configuration for production deployment on GKE

terraform {
  required_version = ">= 1.5"

  backend "gcs" {
    bucket = "ai-gateway-terraform-state"
    prefix = "prod-gcp/terraform.tfstate"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
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
  }
}

# -----------------------------------------------------------------------------
# Variables
# -----------------------------------------------------------------------------

variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "asia-south1"  # Mumbai
}

variable "cluster_name" {
  description = "GKE cluster name"
  type        = string
  default     = "ai-gateway-prod"
}

variable "size" {
  description = "Deployment size (small, medium, large, enterprise)"
  type        = string
  default     = "large"
}

variable "domain_name" {
  description = "Domain name for the gateway"
  type        = string
}

# -----------------------------------------------------------------------------
# Providers
# -----------------------------------------------------------------------------

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

provider "kubernetes" {
  host                   = "https://${module.gke.cluster_endpoint}"
  cluster_ca_certificate = base64decode(module.gke.cluster_ca_certificate)
  token                  = data.google_client_config.default.access_token
}

provider "helm" {
  kubernetes {
    host                   = "https://${module.gke.cluster_endpoint}"
    cluster_ca_certificate = base64decode(module.gke.cluster_ca_certificate)
    token                  = data.google_client_config.default.access_token
  }
}

data "google_client_config" "default" {}

# -----------------------------------------------------------------------------
# GKE Cluster
# -----------------------------------------------------------------------------

module "gke" {
  source = "../../modules/gke"

  project_id   = var.project_id
  cluster_name = var.cluster_name
  region       = var.region
  zones        = ["asia-south1-a", "asia-south1-b", "asia-south1-c"]
  environment  = "production"
  size         = var.size
  enable_gpu   = true
  create_vpc   = true
  network      = "${var.cluster_name}-vpc"
  subnetwork   = "${var.cluster_name}-subnet"
}

# -----------------------------------------------------------------------------
# Cloud SQL (PostgreSQL)
# -----------------------------------------------------------------------------

resource "google_sql_database_instance" "main" {
  name             = "${var.cluster_name}-postgres"
  database_version = "POSTGRES_16"
  region           = var.region
  project          = var.project_id

  deletion_protection = true

  settings {
    tier              = var.size == "enterprise" ? "db-custom-8-32768" : "db-custom-4-16384"
    availability_type = "REGIONAL"
    disk_type         = "PD_SSD"
    disk_size         = var.size == "enterprise" ? 500 : 100
    disk_autoresize   = true

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      start_time                     = "03:00"
      transaction_log_retention_days = 7
      backup_retention_settings {
        retained_backups = 30
      }
    }

    ip_configuration {
      ipv4_enabled    = false
      private_network = module.gke.vpc_id
      require_ssl     = true
    }

    maintenance_window {
      day          = 7  # Sunday
      hour         = 3  # 3 AM
      update_track = "stable"
    }

    insights_config {
      query_insights_enabled  = true
      query_string_length     = 1024
      record_application_tags = true
      record_client_address   = true
    }

    database_flags {
      name  = "max_connections"
      value = "200"
    }
  }
}

resource "google_sql_database" "litellm" {
  name     = "litellm"
  instance = google_sql_database_instance.main.name
  project  = var.project_id
}

resource "google_sql_user" "litellm" {
  name     = "litellm"
  instance = google_sql_database_instance.main.name
  project  = var.project_id
  password = random_password.db_password.result
}

resource "random_password" "db_password" {
  length  = 32
  special = true
}

# -----------------------------------------------------------------------------
# Memorystore Redis
# -----------------------------------------------------------------------------

resource "google_redis_instance" "main" {
  name           = "${var.cluster_name}-redis"
  tier           = "STANDARD_HA"
  memory_size_gb = var.size == "enterprise" ? 16 : 4
  region         = var.region
  project        = var.project_id

  redis_version = "REDIS_7_0"

  authorized_network = module.gke.vpc_id
  connect_mode       = "PRIVATE_SERVICE_ACCESS"

  transit_encryption_mode = "SERVER_AUTHENTICATION"
  auth_enabled           = true

  maintenance_policy {
    weekly_maintenance_window {
      day = "SUNDAY"
      start_time {
        hours   = 3
        minutes = 0
      }
    }
  }

  labels = {
    environment = "production"
    project     = "ai-gateway"
  }
}

# -----------------------------------------------------------------------------
# Secret Manager (for Vault-like functionality)
# -----------------------------------------------------------------------------

resource "google_secret_manager_secret" "llm_keys" {
  for_each = toset(["openai", "anthropic", "xai"])

  secret_id = "ai-gateway-${each.key}-api-key"
  project   = var.project_id

  replication {
    user_managed {
      replicas {
        location = var.region
      }
      replicas {
        location = "asia-south2"  # Delhi for DR
      }
    }
  }

  labels = {
    environment = "production"
    provider    = each.key
  }
}

# -----------------------------------------------------------------------------
# Helm Releases
# -----------------------------------------------------------------------------

# Cert Manager
resource "helm_release" "cert_manager" {
  name             = "cert-manager"
  repository       = "https://charts.jetstack.io"
  chart            = "cert-manager"
  namespace        = "cert-manager"
  create_namespace = true
  version          = "1.14.0"

  set {
    name  = "installCRDs"
    value = "true"
  }

  depends_on = [module.gke]
}

# External Secrets Operator
resource "helm_release" "external_secrets" {
  name             = "external-secrets"
  repository       = "https://charts.external-secrets.io"
  chart            = "external-secrets"
  namespace        = "external-secrets"
  create_namespace = true
  version          = "0.9.0"

  depends_on = [module.gke]
}

# KEDA
resource "helm_release" "keda" {
  name             = "keda"
  repository       = "https://kedacore.github.io/charts"
  chart            = "keda"
  namespace        = "keda"
  create_namespace = true
  version          = "2.13.0"

  depends_on = [module.gke]
}

# Prometheus Stack
resource "helm_release" "prometheus" {
  name             = "prometheus"
  repository       = "https://prometheus-community.github.io/helm-charts"
  chart            = "kube-prometheus-stack"
  namespace        = "monitoring"
  create_namespace = true
  version          = "56.0.0"

  values = [file("${path.module}/values/prometheus.yaml")]

  depends_on = [module.gke]
}

# HashiCorp Vault
resource "helm_release" "vault" {
  name             = "vault"
  repository       = "https://helm.releases.hashicorp.com"
  chart            = "vault"
  namespace        = "vault"
  create_namespace = true
  version          = "0.27.0"

  values = [file("${path.module}/values/vault.yaml")]

  depends_on = [module.gke]
}

# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------

output "cluster_name" {
  description = "GKE cluster name"
  value       = module.gke.cluster_name
}

output "cluster_endpoint" {
  description = "GKE cluster endpoint"
  value       = module.gke.cluster_endpoint
  sensitive   = true
}

output "database_connection" {
  description = "Cloud SQL connection name"
  value       = google_sql_database_instance.main.connection_name
}

output "redis_host" {
  description = "Redis host"
  value       = google_redis_instance.main.host
}

output "kubeconfig_command" {
  description = "Command to get kubeconfig"
  value       = module.gke.kubeconfig_command
}
