output "service_name" {
  description = "Cloud Run service name. Useful for log queries and gcloud invocations."
  value       = google_cloud_run_v2_service.this.name
}

output "service_account_email" {
  description = "Email of the SA the receiver runs as. Use this when granting it access to additional resources outside the module."
  value       = google_service_account.receiver.email
}

output "url" {
  description = <<-EOT
    Public HTTPS URL of the receiver. Pass this to the Pub/Sub push
    subscription's push_endpoint, plus the path "/run_service" the
    receiver mounts.
  EOT
  value       = google_cloud_run_v2_service.this.uri
}
