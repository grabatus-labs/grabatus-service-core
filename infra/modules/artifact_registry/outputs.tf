output "repository_url" {
  description = <<-EOT
    Full Docker registry URL for this repo, suitable for use as an
    image prefix:

      <repository_url>/grabatus-service-core:v0.2.0
      <repository_url>/grabatus-forecasting:v1.0.0
  EOT
  value       = "${google_artifact_registry_repository.this.location}-docker.pkg.dev/${google_artifact_registry_repository.this.project}/${google_artifact_registry_repository.this.repository_id}"
}

output "repository_name" {
  description = "Fully-qualified resource name of the repo, used by IAM bindings outside this module."
  value       = google_artifact_registry_repository.this.name
}
