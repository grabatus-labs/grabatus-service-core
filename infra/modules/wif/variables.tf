variable "project" {
  description = "GCP project ID hosting the workload identity pool."
  type        = string
}

variable "pool_id" {
  description = <<-EOT
    Identifier for the workload identity pool. Must be 4-32 chars,
    starts with a lowercase letter, contains only lowercase letters,
    numbers, and hyphens.
  EOT
  type        = string
}

variable "pool_display_name" {
  description = "Human-readable name shown in the GCP console."
  type        = string
  default     = "GitHub Actions"
}

variable "provider_id" {
  description = "Identifier for the OIDC provider inside the pool."
  type        = string
  default     = "github"
}

variable "github_owner" {
  description = <<-EOT
    GitHub organisation or user that owns the repos allowed to
    impersonate service accounts via this pool. Enforced as the
    attribute condition on the pool provider — any token signed by
    GitHub but issued for a different owner is rejected at federation
    time.
  EOT
  type        = string
}

variable "service_accounts" {
  description = <<-EOT
    Service accounts to provision. Each entry creates one
    google_service_account plus one
    google_service_account_iam_member binding that lets the named
    repository (and optionally a specific GitHub environment)
    impersonate the SA via workloadIdentityUser.

    Map key becomes the SA account_id (must be 6-30 chars, lowercase
    letters/numbers/hyphens, starting with a letter).

    Each value is an object:
      display_name       (required, string) shown in the console
      repository         (required, string) "owner/repo" — the only
                                            repo allowed to assume
                                            this SA
      github_environment (optional, string) restrict to a single
                                            GitHub Actions environment
                                            (e.g., "production"). Use
                                            null to allow any
                                            environment in the repo.
  EOT
  type = map(object({
    display_name       = string
    repository         = string
    github_environment = optional(string)
  }))
  default = {}
}
