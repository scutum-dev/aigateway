# AI Gateway - Demo Environment
# Ephemeral GKE Autopilot + Persistent Cloud SQL
#
# Usage:
#   terraform apply -target=module.persistent  # Once (keeps data)
#   terraform apply                            # Start demo
#   terraform destroy -target=module.gke       # Stop demo (saves money)

terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "asia-south1"
}

variable "domain" {
  description = "Domain name"
  type        = string
  default     = "gateway.deos.dev"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# =============================================================================
# PERSISTENT RESOURCES (always on, keeps data)
# =============================================================================

module "persistent" {
  source = "./modules/persistent"

  project_id = var.project_id
  region     = var.region
}

# =============================================================================
# EPHEMERAL RESOURCES (create/destroy for demos)
# =============================================================================

module "gke" {
  source = "./modules/gke-autopilot"

  project_id   = var.project_id
  region       = var.region
  cluster_name = "gateway-demo"

  # Connect to persistent resources
  database_connection = module.persistent.database_connection
  database_password   = module.persistent.database_password
}

# =============================================================================
# OUTPUTS
# =============================================================================

output "database_ip" {
  value = module.persistent.database_ip
}

output "cluster_name" {
  value = module.gke.cluster_name
}

output "connect_command" {
  value = "gcloud container clusters get-credentials gateway-demo --region ${var.region} --project ${var.project_id}"
}

output "deploy_command" {
  value = "kubectl apply -k kubernetes/overlays/demo"
}
