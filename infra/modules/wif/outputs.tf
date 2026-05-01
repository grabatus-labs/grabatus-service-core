output "pool_id" {
  description = "Resource name of the workload identity pool."
  value       = google_iam_workload_identity_pool.this.name
}

output "provider_resource_name" {
  description = <<-EOT
    Fully-qualified resource name of the OIDC provider, used as the
    workload_identity_provider input to google-github-actions/auth in
    GitHub Actions workflows.
  EOT
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "service_account_emails" {
  description = "Map from SA key → service account email. Used in CI workflows as the service_account input to google-github-actions/auth."
  value = {
    for k, sa in google_service_account.ci :
    k => sa.email
  }
}
