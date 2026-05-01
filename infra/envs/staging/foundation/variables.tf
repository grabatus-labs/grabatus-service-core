variable "gcp_project" {
  description = "GCP project ID for the staging environment."
  type        = string
}

variable "gcp_region" {
  description = "Default region for regional resources."
  type        = string
  default     = "us-east1"
}

variable "environment" {
  description = "Environment name. Used for tagging and naming."
  type        = string
  default     = "staging"

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "environment must be one of: dev, staging, production."
  }
}
