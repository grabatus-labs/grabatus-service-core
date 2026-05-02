variable "gcp_project" {
  description = "GCP project ID for the production environment."
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
  default     = "production"

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "environment must be one of: dev, staging, production."
  }
}

variable "receiver_image_tag" {
  description = "Tag of the grabatus-service-core image to deploy on the shared receiver Cloud Run service."
  type        = string
  default     = "v0.2.0"
}

variable "service_secret_key_secret_id" {
  description = <<-EOT
    Secret Manager secret ID holding SERVICE_SECRET_KEY (JWT signing
    key). The forecasting repo's worker_secret module creates the
    secret resource; this stack only reads it. Convention:
    "service-secret-key".
  EOT
  type        = string
  default     = "service-secret-key"
}

variable "notification_channels" {
  description = <<-EOT
    Resource names of monitoring notification channels (email,
    PagerDuty, Slack) created out-of-band. Pass an empty list to
    skip notifications (useful when the receiver is being
    bootstrapped before paging is wired).
  EOT
  type        = list(string)
  default     = []
}
