# AI Gateway - Variables
# Environment-specific values are set in *.tfvars files

# =============================================================================
# GCP Configuration
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

# =============================================================================
# AWS Configuration
# =============================================================================

variable "aws_region" {
  description = "AWS region for Route53 and Bedrock"
  type        = string
  default     = "ap-south-1"
}

# =============================================================================
# Domain Configuration
# =============================================================================

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

# =============================================================================
# API Keys
# =============================================================================

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

# =============================================================================
# Gateway Configuration
# =============================================================================

variable "litellm_master_key" {
  description = "LiteLLM master key"
  type        = string
  sensitive   = true
  default     = "sk-litellm-demo-key"
}

variable "grafana_password" {
  description = "Grafana admin password"
  type        = string
  sensitive   = true
  default     = "admin"
}

# =============================================================================
# Environment Configuration
# =============================================================================

variable "environment" {
  description = "Environment name (demo, staging, prod)"
  type        = string
  default     = "demo"
}

variable "kustomize_overlay" {
  description = "Kustomize overlay to apply (matches kubernetes/overlays/)"
  type        = string
  default     = "demo-ephemeral"
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
# Budget Configuration
# =============================================================================

variable "budget_amount" {
  description = "Monthly budget amount in INR"
  type        = number
  default     = 2000
}

variable "billing_account" {
  description = "GCP Billing Account ID"
  type        = string
  default     = "0142F7-940143-20933E"
}

variable "budget_alert_email" {
  description = "Email for budget alerts"
  type        = string
  default     = "shankar.deo1771@gmail.com"
}
