# IAM bindings for the receiver.
#
# Two halves:
#   1. The receiver SA gets run.invoker on every worker Cloud Run Job
#      it must be able to dispatch. The list comes from
#      var.worker_jobs and matches the registry's by_name values.
#   2. The Pub/Sub push SA gets run.invoker on the receiver service
#      itself, so authenticated push calls succeed. Toggle by passing
#      a non-null var.pubsub_invoker_email (the forecasting repo's
#      worker_pubsub module produces it).

resource "google_cloud_run_v2_job_iam_member" "receiver_invokes_worker" {
  for_each = var.worker_jobs

  project  = var.project
  location = each.value.region
  name     = each.value.job_name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.receiver.email}"
}

resource "google_cloud_run_v2_service_iam_member" "pubsub_invokes_receiver" {
  count = var.pubsub_invoker_email == null ? 0 : 1

  project  = google_cloud_run_v2_service.this.project
  location = google_cloud_run_v2_service.this.location
  name     = google_cloud_run_v2_service.this.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.pubsub_invoker_email}"
}
