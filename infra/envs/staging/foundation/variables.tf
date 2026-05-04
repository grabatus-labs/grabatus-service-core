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

variable "read_forecasting_worker_state" {
  description = <<-EOT
    Whether to read the forecasting worker stack's remote state
    to discover pubsub_invoker_email. Set to false on the very
    first foundation apply (when the worker stack has never been
    applied yet); flip to true on every subsequent apply so the
    receiver's run.invoker IAM stays in sync. See BOOTSTRAP.md.
  EOT
  type        = bool
  default     = true
}

variable "forecasting_worker_state_bucket" {
  description = <<-EOT
    GCS bucket holding the forecasting worker stack's remote
    state. Defaults to the shared "gbt-tfstate-{env}" bucket.
  EOT
  type        = string
  default     = "gbt-tfstate-staging"
}

variable "forecasting_worker_state_prefix" {
  description = <<-EOT
    Prefix inside forecasting_worker_state_bucket where the
    forecasting worker stack stores its tfstate. Convention:
    gbt-{env}-forecasting/worker.
  EOT
  type        = string
  default     = "gbt-staging-forecasting/worker"
}

variable "pubsub_invoker_email_override" {
  description = <<-EOT
    Manual override for pubsub_invoker_email. When non-null,
    takes priority over the remote-state-derived value. Useful
    for break-glass scenarios where the worker stack is
    temporarily unavailable.
  EOT
  type        = string
  default     = null
}
