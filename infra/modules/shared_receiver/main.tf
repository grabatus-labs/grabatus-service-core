# Shared receiver: Cloud Run v2 Service running the
# grabatus-service-core receiver image.
#
# The receiver's job is small but on the hot path:
#   1. accept Pub/Sub HTTP push,
#   2. validate envelope,
#   3. authorise URIs,
#   4. resolve service.name → worker_job via the registry,
#   5. dispatch the worker via the Cloud Run Jobs API,
#   6. ack Pub/Sub.
#
# Notes:
#   - min_instances defaults to 1 to keep a warm copy. The Pub/Sub
#     ack deadline is 60s; cold starts on a Python 3.12 container
#     with the lib's deps regularly burn 10-20s, which is too close
#     to the limit. The cost is ~5 USD/mo per env.
#   - request_timeout < 60s by validation so a slow receiver fails
#     before the Pub/Sub ack window expires.
#   - The container's role is restricted: no GCS, no Secret Manager
#     (other than SERVICE_SECRET_KEY for JWT signing), no BigQuery.
#     This intentionally cannot read the input data — only the worker
#     can. See spec §8.6.

resource "google_service_account" "receiver" {
  project      = var.project
  account_id   = var.service_account_id
  display_name = "Receiver for ${var.service_name}"
  description  = "Runs the grabatus-service-core shared receiver."
}

resource "google_cloud_run_v2_service" "this" {
  project  = var.project
  location = var.region
  name     = var.service_name

  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = true

  template {
    service_account                  = google_service_account.receiver.email
    timeout                          = "${var.request_timeout}s"
    max_instance_request_concurrency = var.max_concurrency

    scaling {
      min_instance_count = var.min_instance_count
      max_instance_count = var.max_instance_count
    }

    containers {
      image = var.image

      resources {
        limits = {
          cpu    = var.cpu_limit
          memory = var.memory_limit
        }
        cpu_idle = true
      }

      env {
        name  = "GBT_RUNTIME_MODE"
        value = "shared-receiver"
      }

      env {
        name  = "GBT_SERVICE_REGISTRY"
        value = var.service_registry
      }

      env {
        name = "SERVICE_SECRET_KEY"
        value_source {
          secret_key_ref {
            secret  = var.service_secret_key_secret_id
            version = "latest"
          }
        }
      }

      dynamic "env" {
        for_each = var.extra_env
        content {
          name  = env.key
          value = env.value
        }
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
}

# The run.invoker grant for the Pub/Sub OIDC invoker SA lives in
# iam.tf as google_cloud_run_v2_service_iam_member.pubsub_invokes_receiver.
