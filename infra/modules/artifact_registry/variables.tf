variable "project" {
  description = "GCP project ID hosting the Artifact Registry repo."
  type        = string
}

variable "location" {
  description = "Location of the Artifact Registry repo (region or multi-region). Use a region for lower latency from Cloud Run in the same region."
  type        = string
}

variable "repository_id" {
  description = "Repository identifier (the path segment after the project in image URLs). Must be 1-63 chars, lowercase letters/digits/hyphens."
  type        = string
}

variable "description" {
  description = "Human-readable description shown in the GCP console."
  type        = string
  default     = "Container images for Grabatus computational services."
}

variable "writers" {
  description = <<-EOT
    Members granted roles/artifactregistry.writer on the repo. These
    can push new image versions. Each entry must be a fully-qualified
    IAM member string (e.g.,
    "serviceAccount:release-foo@grabatus.iam.gserviceaccount.com").
  EOT
  type        = list(string)
  default     = []
}

variable "readers" {
  description = <<-EOT
    Members granted roles/artifactregistry.reader on the repo. These
    can pull images but not push.
  EOT
  type        = list(string)
  default     = []
}

variable "immutable_tags" {
  description = <<-EOT
    Whether tags pushed to this repo are immutable. true is strongly
    recommended for production-grade repos: it makes vulnerability
    scans and rollback by tag deterministic.
  EOT
  type        = bool
  default     = true
}
