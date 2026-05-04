# Artifact Registry Docker repo + IAM bindings.
#
# Why a single repo per env (instead of per service):
#  - Cloud Run pulls images by full URL; one shared repo simplifies
#    the URL pattern (us-east1-docker.pkg.dev/$PROJECT/services/$image).
#  - IAM is uniform: any release SA pushes here, any deploy SA pulls
#    here — service-level isolation comes from image names, not repos.
#
# Why immutable_tags defaults to true:
#  - tfsec recommends it (CRITICAL "AVD-GCP-0009" otherwise).
#  - "v1.0.0" should never refer to a different binary tomorrow than
#    today; mutable tags break rollback and vuln tracking.
#  - Forces release pipelines to push semver-tagged builds (which is
#    what we want anyway).

resource "google_artifact_registry_repository" "this" {
  project       = var.project
  location      = var.location
  repository_id = var.repository_id
  description   = var.description
  format        = "DOCKER"

  docker_config {
    immutable_tags = var.immutable_tags
  }
}

resource "google_artifact_registry_repository_iam_member" "writer" {
  for_each = toset(var.writers)

  project    = google_artifact_registry_repository.this.project
  location   = google_artifact_registry_repository.this.location
  repository = google_artifact_registry_repository.this.repository_id
  role       = "roles/artifactregistry.writer"
  member     = each.value
}

resource "google_artifact_registry_repository_iam_member" "reader" {
  for_each = toset(var.readers)

  project    = google_artifact_registry_repository.this.project
  location   = google_artifact_registry_repository.this.location
  repository = google_artifact_registry_repository.this.repository_id
  role       = "roles/artifactregistry.reader"
  member     = each.value
}
