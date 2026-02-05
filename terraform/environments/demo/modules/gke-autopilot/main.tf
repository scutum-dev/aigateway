# GKE Autopilot - Ephemeral compute for demos
# Destroy when not demoing to save costs

variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "cluster_name" {
  type    = string
  default = "gateway-demo"
}

variable "database_connection" {
  type = string
}

variable "database_password" {
  type      = string
  sensitive = true
}

# Get VPC from persistent module
data "google_compute_network" "main" {
  name    = "gateway-demo-vpc"
  project = var.project_id
}

data "google_compute_subnetwork" "main" {
  name    = "gateway-demo-subnet"
  project = var.project_id
  region  = var.region
}

# GKE Autopilot Cluster
resource "google_container_cluster" "main" {
  name     = var.cluster_name
  location = var.region
  project  = var.project_id

  # Autopilot mode
  enable_autopilot = true

  # Network config
  network    = data.google_compute_network.main.name
  subnetwork = data.google_compute_subnetwork.main.name

  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  # Private cluster
  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = "172.16.0.0/28"
  }

  # Allow access from anywhere (demo only)
  master_authorized_networks_config {
    cidr_blocks {
      cidr_block   = "0.0.0.0/0"
      display_name = "All"
    }
  }

  # Release channel
  release_channel {
    channel = "REGULAR"
  }

  # Workload identity
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  deletion_protection = false
}

# Create namespace and secrets
resource "google_service_account" "workload" {
  account_id   = "gateway-demo-workload"
  display_name = "Gateway Demo Workload Identity"
  project      = var.project_id
}

# Grant Cloud SQL access
resource "google_project_iam_member" "cloudsql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.workload.email}"
}

# Grant Secret Manager access
resource "google_project_iam_member" "secrets" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.workload.email}"
}

# Outputs
output "cluster_name" {
  value = google_container_cluster.main.name
}

output "cluster_endpoint" {
  value     = google_container_cluster.main.endpoint
  sensitive = true
}

output "workload_identity_sa" {
  value = google_service_account.workload.email
}
