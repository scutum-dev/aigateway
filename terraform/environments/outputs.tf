# AI Gateway - Outputs

output "cluster_name" {
  description = "GKE cluster name"
  value       = google_container_cluster.main.name
}

output "cluster_endpoint" {
  description = "GKE cluster endpoint"
  value       = google_container_cluster.main.endpoint
  sensitive   = true
}

output "artifact_registry" {
  description = "Docker registry URL for images"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/gateway-images"
}

output "gateway_url" {
  description = "Gateway URL"
  value       = "https://${local.full_domain}"
}

output "ingress_ip" {
  description = "Run: kubectl -n ingress-nginx get svc ingress-nginx-controller -o jsonpath='{.status.loadBalancer.ingress[0].ip}'"
  value       = "Check with kubectl after apply"
}

output "api_key" {
  description = "LiteLLM API key"
  value       = var.litellm_master_key
  sensitive   = true
}

output "credentials" {
  description = "Service credentials"
  sensitive   = true
  value = {
    gateway_api_key  = var.litellm_master_key
    grafana_user     = "admin"
    grafana_password = var.grafana_password
    admin_ui_api_key = var.litellm_master_key
  }
}

output "urls" {
  description = "Service URLs"
  value = {
    gateway        = "https://${local.full_domain}"
    api_docs       = "https://${local.full_domain}/docs"
    health         = "https://${local.full_domain}/health/readiness"
    admin_ui       = "https://${local.full_domain}/admin"
    admin_api      = "https://${local.full_domain}/admin-api"
    grafana        = "https://${local.full_domain}/grafana"
    cost_predictor = "https://${local.full_domain}/cost-predictor"
    policy_router  = "https://${local.full_domain}/policy-router"
    workflows      = "https://${local.full_domain}/workflows"
    mcp_gateway    = "https://${local.full_domain}/mcp"
    semantic_cache = "https://${local.full_domain}/semantic-cache"
  }
}

output "environment_config" {
  description = "Environment configuration"
  value = {
    environment         = var.environment
    replicas            = var.litellm_replicas
    hpa_min             = var.min_replicas
    hpa_max             = var.max_replicas
    deletion_protection = var.deletion_protection
  }
}

output "namespace" {
  description = "Kubernetes namespace"
  value       = local.namespace
}

output "access_commands" {
  description = "Commands to access the environment"
  sensitive   = true
  value       = <<-EOT

    === AI Gateway ${upper(var.environment)} Environment Ready ===

    Gateway URL: https://${local.full_domain}
    API Key: ${var.litellm_master_key}
    Environment: ${var.environment}
    Replicas: ${var.litellm_replicas} (HPA: ${var.min_replicas}-${var.max_replicas})

    URLs:
      Gateway API:  https://${local.full_domain}
      API Docs:     https://${local.full_domain}/docs
      Admin UI:     https://${local.full_domain}/admin
      Admin API:    https://${local.full_domain}/admin-api
      Grafana:      https://${local.full_domain}/grafana (admin/${var.grafana_password})

    Connect to cluster:
      gcloud container clusters get-credentials ${local.cluster_name} --region ${var.region} --project ${var.project_id}

    Test API:
      curl https://${local.full_domain}/health/readiness
      curl https://${local.full_domain}/v1/models -H "Authorization: Bearer ${var.litellm_master_key}"

    ${var.deletion_protection ? "WARNING: Deletion protection ENABLED - terraform destroy will fail" : "Destroy when done: make destroy ENV=${var.environment}"}

  EOT
}
