# Persistent Resources - Cloud SQL + Redis
# These stay running to preserve data between demos

variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

# VPC for private connectivity
resource "google_compute_network" "main" {
  name                    = "gateway-demo-vpc"
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

# Private service access for Cloud SQL
resource "google_compute_global_address" "private_ip" {
  name          = "gateway-demo-private-ip"
  project       = var.project_id
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.main.id
}

resource "google_service_networking_connection" "private" {
  network                 = google_compute_network.main.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip.name]
}

# Cloud SQL PostgreSQL (persistent)
resource "google_sql_database_instance" "main" {
  name             = "gateway-demo-db"
  database_version = "POSTGRES_16"
  region           = var.region
  project          = var.project_id

  deletion_protection = false  # Demo only

  settings {
    tier              = "db-f1-micro"  # Cheapest: ~$10/mo
    availability_type = "ZONAL"        # No HA for demo
    disk_size         = 10
    disk_type         = "PD_SSD"
    disk_autoresize   = true

    ip_configuration {
      ipv4_enabled    = true  # Allow public for easy access
      private_network = google_compute_network.main.id
    }

    backup_configuration {
      enabled    = true
      start_time = "03:00"
    }
  }

  depends_on = [google_service_networking_connection.private]
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
  password = random_password.db.result
}

resource "random_password" "db" {
  length  = 24
  special = false
}

# Store password in Secret Manager
resource "google_secret_manager_secret" "db_password" {
  secret_id = "gateway-demo-db-password"
  project   = var.project_id

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = random_password.db.result
}

# Memorystore Redis (persistent)
resource "google_redis_instance" "main" {
  name           = "gateway-demo-redis"
  tier           = "BASIC"  # Cheapest: ~$35/mo
  memory_size_gb = 1
  region         = var.region
  project        = var.project_id

  redis_version     = "REDIS_7_0"
  authorized_network = google_compute_network.main.id
  connect_mode      = "PRIVATE_SERVICE_ACCESS"

  depends_on = [google_service_networking_connection.private]
}

# Outputs
output "database_ip" {
  value = google_sql_database_instance.main.public_ip_address
}

output "database_private_ip" {
  value = google_sql_database_instance.main.private_ip_address
}

output "database_connection" {
  value = google_sql_database_instance.main.connection_name
}

output "database_password" {
  value     = random_password.db.result
  sensitive = true
}

output "redis_host" {
  value = google_redis_instance.main.host
}

output "vpc_id" {
  value = google_compute_network.main.id
}

output "subnet_id" {
  value = google_compute_subnetwork.main.id
}
