variable "project" {
  description = "GCP project ID hosting the alert policies."
  type        = string
}

variable "environment" {
  description = "Environment name. Used in alert display names so the on-call sees \"[production] receiver error spike\" rather than just \"receiver error spike\"."
  type        = string

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "environment must be one of: dev, staging, production."
  }
}

variable "notification_channels" {
  description = <<-EOT
    Resource names of google_monitoring_notification_channel objects
    that receive alert notifications. Created out-of-band (typically
    one channel per medium per env: email-oncall, pagerduty, slack)
    and passed in here so this module stays oblivious to channel
    plumbing.
  EOT
  type        = list(string)
  default     = []
}

variable "receiver_service_name" {
  description = "Cloud Run service name of the shared receiver. Used to scope the receiver-specific alerts."
  type        = string
}

variable "error_rate_threshold" {
  description = "Receiver 5xx error rate (per second) above which the warning alert fires."
  type        = number
  default     = 0.5
}

variable "auto_close_duration" {
  description = "Time without breaching the condition after which an open incident auto-closes (Terraform duration string, e.g. \"604800s\" = 7 days)."
  type        = string
  default     = "604800s"
}
