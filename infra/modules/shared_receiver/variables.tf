variable "project" {
  description = "GCP project ID hosting the receiver."
  type        = string
}

variable "region" {
  description = "Region for the Cloud Run service."
  type        = string
  default     = "us-east1"
}

variable "service_name" {
  description = "Cloud Run service name. Convention: gbt-{env}-receiver."
  type        = string
}

variable "service_account_id" {
  description = "Account ID for the dedicated SA the receiver runs as. Convention: gbt-{env}-receiver-sa."
  type        = string
}

variable "image" {
  description = <<-EOT
    Full container image reference, e.g.
    us-east1-docker.pkg.dev/grabatus/services/grabatus-service-core:v0.2.0.
    The Plan 2D Artifact Registry module exposes the URL prefix as an
    output; the consumer interpolates the tag.
  EOT
  type        = string
}

variable "service_registry" {
  description = <<-EOT
    Value passed to the GBT_SERVICE_REGISTRY env var. JSON or the
    short comma form accepted by ServiceRegistry.from_env_string,
    e.g. {"by_name": {"forecast": "gbt-dev-forecasting-worker"}}.
  EOT
  type        = string
}

variable "service_secret_key_secret_id" {
  description = <<-EOT
    Secret Manager secret ID (NOT a version). The receiver mounts the
    latest enabled version into SERVICE_SECRET_KEY at runtime. Created
    by the worker_secret module in the forecasting repo, but the
    receiver also reads it (it signs JWT webhook receipts).
  EOT
  type        = string
}

variable "extra_env" {
  description = "Additional non-secret env vars merged into the container env."
  type        = map(string)
  default     = {}
}

variable "min_instance_count" {
  description = "Lower bound on Cloud Run instance count. 1 keeps a warm instance for low-latency Pub/Sub ack."
  type        = number
  default     = 1
}

variable "max_instance_count" {
  description = "Upper bound on Cloud Run instance count."
  type        = number
  default     = 10
}

variable "request_timeout" {
  description = <<-EOT
    Per-request timeout in seconds. Pub/Sub push ack deadline is 60s
    by default; receiver MUST respond within that window. Set this
    below the ack deadline.
  EOT
  type        = number
  default     = 50

  validation {
    condition     = var.request_timeout >= 10 && var.request_timeout <= 60
    error_message = "request_timeout must be between 10 and 60 seconds (Pub/Sub ack deadline ceiling)."
  }
}

variable "max_concurrency" {
  description = "Max concurrent requests per instance."
  type        = number
  default     = 80
}

variable "cpu_limit" {
  description = "Per-instance CPU limit (Cloud Run cpu format, e.g. \"1\")."
  type        = string
  default     = "1"
}

variable "memory_limit" {
  description = "Per-instance memory limit (Cloud Run memory format, e.g. \"512Mi\")."
  type        = string
  default     = "512Mi"
}

variable "worker_jobs" {
  description = <<-EOT
    Cloud Run Jobs the receiver may dispatch. Each entry grants the
    receiver SA roles/run.invoker on the named job, scoped to its
    region.

    Map key is a stable identifier (used inside Terraform only); each
    value is { job_name, region }.
  EOT
  type = map(object({
    job_name = string
    region   = string
  }))
  default = {}
}

variable "pubsub_invoker_email" {
  description = <<-EOT
    Email of the SA that Pub/Sub uses to call /run_service. The
    forecasting repo's worker_pubsub module creates this SA; passing
    it here grants it run.invoker on the receiver service. Set to
    null to skip the binding (e.g., when standing up the receiver
    before the Pub/Sub stack is wired).
  EOT
  type        = string
  default     = null
}
