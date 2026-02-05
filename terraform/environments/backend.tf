# AI Gateway - Terraform Backend Configuration
#
# Uses GCS backend with prefix for multi-environment state isolation.
# The prefix is set via -backend-config during terraform init:
#
#   terraform init -backend-config="prefix=demo"
#   terraform init -backend-config="prefix=staging"
#   terraform init -backend-config="prefix=prod"

terraform {
  required_version = ">= 1.5"

  backend "gcs" {
    bucket = "aigateway-demo-tfstate"
    # prefix is set via -backend-config="prefix=ENV"
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
