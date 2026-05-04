# Root module for the staging environment's foundation stack.
#
# Wires the WIF, Artifact Registry, shared receiver, and common
# alerts modules. Per-env values land in terraform.tfvars; the
# defaults in variables.tf cover everything else.
#
# Reading order:
#   1. WIF establishes the trust between GitHub Actions and GCP.
#   2. Artifact Registry hosts the container images CI pushes.
#   3. The shared receiver runs the lib's receiver image.
#   4. Common alerts watch the receiver and security incidents.

# Forecasting worker stack remote state (optional).
#
# The worker stack outputs pubsub_invoker_email — the SA that
# Pub/Sub uses to OIDC-sign push requests to the receiver. The
# foundation grants run.invoker on the receiver to that email.
# On the very first apply (worker stack never applied), set
# read_forecasting_worker_state = false; flip to true after.
data "terraform_remote_state" "forecasting_worker" {
  count = var.read_forecasting_worker_state ? 1 : 0

  backend = "gcs"

  config = {
    bucket = var.forecasting_worker_state_bucket
    prefix = var.forecasting_worker_state_prefix
  }

  defaults = {
    pubsub_invoker_email = null
  }
}

locals {
  prefix     = "gbt-${var.environment}"
  github_org = "rodolphomacedo"

  pubsub_invoker_email = (
    var.pubsub_invoker_email_override != null
    ? var.pubsub_invoker_email_override
    : (var.read_forecasting_worker_state
      ? try(data.terraform_remote_state.forecasting_worker[0].outputs.pubsub_invoker_email, null)
      : null
    )
  )
}

module "wif" {
  source       = "../../../modules/wif"
  project      = var.gcp_project
  pool_id      = "github-actions-pool"
  github_owner = local.github_org

  service_accounts = {
    "ci-service-core" = {
      display_name = "CI for grabatus-service-core"
      repository   = "${local.github_org}/grabatus-service-core"
    }
    "release-service-core" = {
      display_name = "Release pipeline for grabatus-service-core"
      repository   = "${local.github_org}/grabatus-service-core"
    }
    "deploy-service-core" = {
      display_name       = "Terraform apply for grabatus-service-core (${var.environment})"
      repository         = "${local.github_org}/grabatus-service-core"
      github_environment = var.environment
    }
    "ci-forecasting" = {
      display_name = "CI for grabatus-forecasting"
      repository   = "${local.github_org}/grabatus-forecasting"
    }
    "release-forecasting" = {
      display_name = "Release pipeline for grabatus-forecasting"
      repository   = "${local.github_org}/grabatus-forecasting"
    }
    "deploy-forecasting" = {
      display_name       = "Terraform apply for grabatus-forecasting (${var.environment})"
      repository         = "${local.github_org}/grabatus-forecasting"
      github_environment = var.environment
    }
  }
}

module "artifact_registry" {
  source        = "../../../modules/artifact_registry"
  project       = var.gcp_project
  location      = var.gcp_region
  repository_id = "services"

  writers = [
    "serviceAccount:${module.wif.service_account_emails["release-service-core"]}",
    "serviceAccount:${module.wif.service_account_emails["release-forecasting"]}",
  ]

  readers = [
    "serviceAccount:${module.wif.service_account_emails["deploy-service-core"]}",
    "serviceAccount:${module.wif.service_account_emails["deploy-forecasting"]}",
  ]
}

module "shared_receiver" {
  source             = "../../../modules/shared_receiver"
  project            = var.gcp_project
  region             = var.gcp_region
  service_name       = "${local.prefix}-receiver"
  service_account_id = "${local.prefix}-receiver-sa"
  image              = "${module.artifact_registry.repository_url}/grabatus-service-core:${var.receiver_image_tag}"

  # The forecasting worker stack populates this secret. The receiver
  # only reads it for JWT signing; the worker reads it for both
  # signing and validating webhook responses.
  service_secret_key_secret_id = var.service_secret_key_secret_id

  service_registry = jsonencode({
    by_name = {
      forecast = "${local.prefix}-forecasting-worker"
    }
  })

  worker_jobs = {
    "forecasting" = {
      job_name = "${local.prefix}-forecasting-worker"
      region   = var.gcp_region
    }
  }

  # Sourced from the forecasting worker stack via remote state
  # (see local.pubsub_invoker_email above). On the bootstrap
  # apply this is null and the receiver applies without the
  # run.invoker binding; the second apply picks it up.
  pubsub_invoker_email = local.pubsub_invoker_email
}

module "alerts" {
  source                = "../../../modules/alerts_common"
  project               = var.gcp_project
  environment           = var.environment
  receiver_service_name = module.shared_receiver.service_name
  notification_channels = var.notification_channels
}
