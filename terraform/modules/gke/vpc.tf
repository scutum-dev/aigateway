# AI Gateway Platform - GCP VPC Module
# Production-ready VPC for GKE in Mumbai (asia-south1)

# -----------------------------------------------------------------------------
# Variables (additional to main.tf)
# -----------------------------------------------------------------------------

variable "create_vpc" {
  description = "Whether to create a new VPC or use existing"
  type        = bool
  default     = true
}

variable "vpc_cidr" {
  description = "Primary CIDR range for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

# -----------------------------------------------------------------------------
# VPC Network
# -----------------------------------------------------------------------------

resource "google_compute_network" "main" {
  count = var.create_vpc ? 1 : 0

  name                            = "${var.cluster_name}-vpc"
  project                         = var.project_id
  auto_create_subnetworks         = false
  routing_mode                    = "REGIONAL"
  delete_default_routes_on_create = false
}

# -----------------------------------------------------------------------------
# Subnets
# -----------------------------------------------------------------------------

resource "google_compute_subnetwork" "main" {
  count = var.create_vpc ? 1 : 0

  name          = "${var.cluster_name}-subnet"
  project       = var.project_id
  region        = var.region
  network       = google_compute_network.main[0].id
  ip_cidr_range = var.vpc_cidr

  # Secondary ranges for GKE pods and services
  secondary_ip_range {
    range_name    = "${var.cluster_name}-pods"
    ip_cidr_range = "10.1.0.0/16"
  }

  secondary_ip_range {
    range_name    = "${var.cluster_name}-services"
    ip_cidr_range = "10.2.0.0/20"
  }

  private_ip_google_access = true

  log_config {
    aggregation_interval = "INTERVAL_5_SEC"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }
}

# -----------------------------------------------------------------------------
# Cloud NAT (for private nodes to access internet)
# -----------------------------------------------------------------------------

resource "google_compute_router" "main" {
  count = var.create_vpc ? 1 : 0

  name    = "${var.cluster_name}-router"
  project = var.project_id
  region  = var.region
  network = google_compute_network.main[0].id
}

resource "google_compute_router_nat" "main" {
  count = var.create_vpc ? 1 : 0

  name                               = "${var.cluster_name}-nat"
  project                            = var.project_id
  router                             = google_compute_router.main[0].name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

# -----------------------------------------------------------------------------
# Firewall Rules
# -----------------------------------------------------------------------------

# Allow internal communication
resource "google_compute_firewall" "internal" {
  count = var.create_vpc ? 1 : 0

  name    = "${var.cluster_name}-allow-internal"
  project = var.project_id
  network = google_compute_network.main[0].id

  allow {
    protocol = "tcp"
  }

  allow {
    protocol = "udp"
  }

  allow {
    protocol = "icmp"
  }

  source_ranges = [var.vpc_cidr, "10.1.0.0/16", "10.2.0.0/20"]
}

# Allow health checks from GCP load balancers
resource "google_compute_firewall" "health_check" {
  count = var.create_vpc ? 1 : 0

  name    = "${var.cluster_name}-allow-health-check"
  project = var.project_id
  network = google_compute_network.main[0].id

  allow {
    protocol = "tcp"
  }

  # GCP health check ranges
  source_ranges = ["35.191.0.0/16", "130.211.0.0/22"]
  target_tags   = ["${var.cluster_name}-cpu", "${var.cluster_name}-gpu"]
}

# Allow SSH via IAP
resource "google_compute_firewall" "iap_ssh" {
  count = var.create_vpc ? 1 : 0

  name    = "${var.cluster_name}-allow-iap-ssh"
  project = var.project_id
  network = google_compute_network.main[0].id

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  # IAP range
  source_ranges = ["35.235.240.0/20"]
}

# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------

output "vpc_id" {
  description = "VPC ID"
  value       = var.create_vpc ? google_compute_network.main[0].id : null
}

output "vpc_name" {
  description = "VPC name"
  value       = var.create_vpc ? google_compute_network.main[0].name : var.network
}

output "subnet_name" {
  description = "Subnet name"
  value       = var.create_vpc ? google_compute_subnetwork.main[0].name : var.subnetwork
}

output "subnet_id" {
  description = "Subnet ID"
  value       = var.create_vpc ? google_compute_subnetwork.main[0].id : null
}
