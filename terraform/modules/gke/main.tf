# AI Gateway Platform - GKE Module
# Production-ready GKE cluster with GPU support for Mumbai (asia-south1)

terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
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

variable "cluster_name" {
  description = "Name of the GKE cluster"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "asia-south1"  # Mumbai
}

variable "zones" {
  description = "GCP zones within the region"
  type        = list(string)
  default     = ["asia-south1-a", "asia-south1-b", "asia-south1-c"]
}

variable "network" {
  description = "VPC network name"
  type        = string
}

variable "subnetwork" {
  description = "VPC subnetwork name"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "size" {
  description = "Cluster size profile (small, medium, large, enterprise)"
  type        = string
  default     = "medium"
}

variable "enable_gpu" {
  description = "Enable GPU node pools"
  type        = bool
  default     = true
}

# -----------------------------------------------------------------------------
# Locals - Size Configurations
# -----------------------------------------------------------------------------

locals {
  size_configs = {
    small = {
      cpu_machine_type   = "n2-standard-4"
      cpu_node_count     = 1
      cpu_min_count      = 1
      cpu_max_count      = 3
      gpu_machine_type   = "n1-standard-4"
      gpu_accelerator    = "nvidia-tesla-t4"
      gpu_count          = 1
      gpu_node_count     = 1
      gpu_min_count      = 0
      gpu_max_count      = 2
    }
    medium = {
      cpu_machine_type   = "n2-standard-8"
      cpu_node_count     = 2
      cpu_min_count      = 2
      cpu_max_count      = 5
      gpu_machine_type   = "n1-standard-8"
      gpu_accelerator    = "nvidia-tesla-t4"
      gpu_count          = 1
      gpu_node_count     = 2
      gpu_min_count      = 1
      gpu_max_count      = 4
    }
    large = {
      cpu_machine_type   = "n2-standard-16"
      cpu_node_count     = 3
      cpu_min_count      = 3
      cpu_max_count      = 10
      gpu_machine_type   = "a2-highgpu-1g"
      gpu_accelerator    = "nvidia-tesla-a100"
      gpu_count          = 1
      gpu_node_count     = 2
      gpu_min_count      = 2
      gpu_max_count      = 8
    }
    enterprise = {
      cpu_machine_type   = "n2-standard-32"
      cpu_node_count     = 5
      cpu_min_count      = 5
      cpu_max_count      = 20
      gpu_machine_type   = "a2-highgpu-4g"
      gpu_accelerator    = "nvidia-tesla-a100"
      gpu_count          = 4
      gpu_node_count     = 4
      gpu_min_count      = 2
      gpu_max_count      = 16
    }
  }

  config = local.size_configs[var.size]

  labels = {
    environment = var.environment
    managed_by  = "terraform"
    project     = "ai-gateway"
  }
}

# -----------------------------------------------------------------------------
# Service Account for GKE Nodes
# -----------------------------------------------------------------------------

resource "google_service_account" "gke_nodes" {
  account_id   = "${var.cluster_name}-nodes"
  display_name = "GKE Node Service Account for ${var.cluster_name}"
  project      = var.project_id
}

resource "google_project_iam_member" "gke_nodes_roles" {
  for_each = toset([
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/monitoring.viewer",
    "roles/stackdriver.resourceMetadata.writer",
    "roles/artifactregistry.reader",
    "roles/storage.objectViewer"
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.gke_nodes.email}"
}

# -----------------------------------------------------------------------------
# GKE Cluster
# -----------------------------------------------------------------------------

resource "google_container_cluster" "main" {
  provider = google-beta

  name     = var.cluster_name
  location = var.region
  project  = var.project_id

  # Regional cluster with nodes in specific zones
  node_locations = var.zones

  # Use release channel for automatic upgrades
  release_channel {
    channel = var.environment == "prod" ? "STABLE" : "REGULAR"
  }

  # VPC-native cluster
  network    = var.network
  subnetwork = var.subnetwork

  networking_mode = "VPC_NATIVE"
  ip_allocation_policy {
    cluster_ipv4_cidr_block  = "/16"
    services_ipv4_cidr_block = "/22"
  }

  # Private cluster configuration
  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = var.environment == "prod"
    master_ipv4_cidr_block  = "172.16.0.0/28"
  }

  # Master authorized networks
  master_authorized_networks_config {
    dynamic "cidr_blocks" {
      for_each = var.environment == "prod" ? [] : [1]
      content {
        cidr_block   = "0.0.0.0/0"
        display_name = "All (dev/staging only)"
      }
    }
  }

  # Workload identity
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  # Binary authorization
  binary_authorization {
    evaluation_mode = var.environment == "prod" ? "PROJECT_SINGLETON_POLICY_ENFORCE" : "DISABLED"
  }

  # Security configuration
  database_encryption {
    state    = "ENCRYPTED"
    key_name = google_kms_crypto_key.gke.id
  }

  # Remove default node pool, we'll create custom ones
  remove_default_node_pool = true
  initial_node_count       = 1

  # Addons
  addons_config {
    http_load_balancing {
      disabled = false
    }
    horizontal_pod_autoscaling {
      disabled = false
    }
    gce_persistent_disk_csi_driver_config {
      enabled = true
    }
    gcs_fuse_csi_driver_config {
      enabled = true
    }
  }

  # Logging and monitoring
  logging_config {
    enable_components = ["SYSTEM_COMPONENTS", "WORKLOADS"]
  }

  monitoring_config {
    enable_components = ["SYSTEM_COMPONENTS"]
    managed_prometheus {
      enabled = true
    }
  }

  # Maintenance window (2 AM - 6 AM IST on weekends)
  maintenance_policy {
    recurring_window {
      start_time = "2026-01-01T20:30:00Z"  # 2 AM IST
      end_time   = "2026-01-02T00:30:00Z"  # 6 AM IST
      recurrence = "FREQ=WEEKLY;BYDAY=SA,SU"
    }
  }

  resource_labels = local.labels

  depends_on = [
    google_project_iam_member.gke_nodes_roles,
    google_kms_crypto_key_iam_member.gke
  ]
}

# -----------------------------------------------------------------------------
# KMS for Encryption
# -----------------------------------------------------------------------------

resource "google_kms_key_ring" "gke" {
  name     = "${var.cluster_name}-keyring"
  location = var.region
  project  = var.project_id
}

resource "google_kms_crypto_key" "gke" {
  name            = "${var.cluster_name}-key"
  key_ring        = google_kms_key_ring.gke.id
  rotation_period = "7776000s"  # 90 days

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_kms_crypto_key_iam_member" "gke" {
  crypto_key_id = google_kms_crypto_key.gke.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:service-${data.google_project.current.number}@container-engine-robot.iam.gserviceaccount.com"
}

data "google_project" "current" {
  project_id = var.project_id
}

# -----------------------------------------------------------------------------
# Node Pools
# -----------------------------------------------------------------------------

# CPU Node Pool (System + General workloads)
resource "google_container_node_pool" "cpu" {
  name       = "${var.cluster_name}-cpu"
  location   = var.region
  cluster    = google_container_cluster.main.name
  project    = var.project_id

  initial_node_count = local.config.cpu_node_count

  autoscaling {
    min_node_count = local.config.cpu_min_count
    max_node_count = local.config.cpu_max_count
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  upgrade_settings {
    max_surge       = 1
    max_unavailable = 0
  }

  node_config {
    machine_type = local.config.cpu_machine_type

    disk_size_gb = 100
    disk_type    = "pd-ssd"

    service_account = google_service_account.gke_nodes.email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }

    labels = merge(local.labels, {
      node_type = "cpu"
      workload  = "general"
    })

    tags = ["${var.cluster_name}-cpu"]

    metadata = {
      disable-legacy-endpoints = "true"
    }
  }
}

# GPU Node Pool (vLLM inference)
resource "google_container_node_pool" "gpu" {
  count = var.enable_gpu ? 1 : 0

  name       = "${var.cluster_name}-gpu"
  location   = var.region
  cluster    = google_container_cluster.main.name
  project    = var.project_id

  # GPU nodes only in specific zones where GPUs are available
  node_locations = [var.zones[0]]

  initial_node_count = local.config.gpu_node_count

  autoscaling {
    min_node_count = local.config.gpu_min_count
    max_node_count = local.config.gpu_max_count
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  node_config {
    machine_type = local.config.gpu_machine_type

    guest_accelerator {
      type  = local.config.gpu_accelerator
      count = local.config.gpu_count
      gpu_driver_installation_config {
        gpu_driver_version = "LATEST"
      }
    }

    disk_size_gb = 200
    disk_type    = "pd-ssd"

    service_account = google_service_account.gke_nodes.email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }

    labels = merge(local.labels, {
      node_type                = "gpu"
      workload                 = "inference"
      "nvidia.com/gpu.present" = "true"
    })

    taint {
      key    = "nvidia.com/gpu"
      value  = "true"
      effect = "NO_SCHEDULE"
    }

    tags = ["${var.cluster_name}-gpu"]

    metadata = {
      disable-legacy-endpoints = "true"
    }
  }
}

# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------

output "cluster_name" {
  description = "GKE cluster name"
  value       = google_container_cluster.main.name
}

output "cluster_endpoint" {
  description = "GKE cluster endpoint"
  value       = google_container_cluster.main.endpoint
  sensitive   = true
}

output "cluster_ca_certificate" {
  description = "GKE cluster CA certificate"
  value       = google_container_cluster.main.master_auth[0].cluster_ca_certificate
  sensitive   = true
}

output "cluster_location" {
  description = "GKE cluster location"
  value       = google_container_cluster.main.location
}

output "node_service_account" {
  description = "Service account email for nodes"
  value       = google_service_account.gke_nodes.email
}

output "kubeconfig_command" {
  description = "Command to get kubeconfig"
  value       = "gcloud container clusters get-credentials ${google_container_cluster.main.name} --region ${var.region} --project ${var.project_id}"
}
