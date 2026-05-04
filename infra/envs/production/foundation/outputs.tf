output "receiver_url" {
  description = <<-EOT
    Public HTTPS URL of the shared receiver. The forecasting worker
    stack reads this via remote_state and appends "/run_service"
    when configuring the Pub/Sub push subscription.
  EOT
  value       = module.shared_receiver.url
}

output "receiver_service_name" {
  description = "Cloud Run service name of the receiver."
  value       = module.shared_receiver.service_name
}

output "receiver_service_account_email" {
  description = "Email of the receiver's runtime SA."
  value       = module.shared_receiver.service_account_email
}

output "artifact_registry_repository_url" {
  description = <<-EOT
    Full Docker registry URL prefix for service images. Append
    "/<image-name>:<tag>" to obtain a pullable reference.
  EOT
  value       = module.artifact_registry.repository_url
}

output "deploy_service_core_email" {
  description = "Email of the WIF-bound deploy SA for grabatus-service-core."
  value       = module.wif.service_account_emails["deploy-service-core"]
}

output "deploy_forecasting_email" {
  description = <<-EOT
    Email of the WIF-bound deploy SA for grabatus-forecasting. The
    forecasting worker stack references this to grant the deploy SA
    iam.serviceAccountUser on the worker runtime SAs it manages.
  EOT
  value       = module.wif.service_account_emails["deploy-forecasting"]
}
