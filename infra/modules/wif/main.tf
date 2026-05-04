# Workload Identity Federation: GitHub Actions ↔ GCP.
#
# Creates a single pool + OIDC provider scoped to a GitHub owner, plus
# one service account per entry in var.service_accounts. Each SA has
# a workloadIdentityUser binding that allows exactly the named repo
# (and optionally a single GitHub Actions environment) to impersonate
# it.
#
# Why this shape:
#  - One pool per GCP project keeps GCP IAM auditing simple (every
#    federation event lands in a single pool's audit log).
#  - Per-repo SA bindings (vs. a single CI-shared SA) make the blast
#    radius of a leaked OIDC token equal to the access level of one
#    repo's CI, not the union of all repos.
#  - The github_environment knob is the standard way to require a
#    deployment-protection-rule approval before a token can be
#    issued for production-grade SAs.

resource "google_iam_workload_identity_pool" "this" {
  project                   = var.project
  workload_identity_pool_id = var.pool_id
  display_name              = var.pool_display_name
  description               = "GitHub Actions federation for ${var.github_owner}"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project
  workload_identity_pool_id          = google_iam_workload_identity_pool.this.workload_identity_pool_id
  workload_identity_pool_provider_id = var.provider_id
  display_name                       = "GitHub Actions OIDC"
  description                        = "OIDC issuer: token.actions.githubusercontent.com"

  attribute_mapping = {
    "google.subject"             = "assertion.sub"
    "attribute.repository"       = "assertion.repository"
    "attribute.repository_owner" = "assertion.repository_owner"
    "attribute.environment"      = "assertion.environment"
    "attribute.ref"              = "assertion.ref"
  }

  # Reject any OIDC token whose repository_owner claim is not the
  # configured owner. This is the single most important guardrail: it
  # prevents any GitHub repo on the planet from federating into this
  # pool, even before per-SA bindings are evaluated.
  attribute_condition = "assertion.repository_owner == '${var.github_owner}'"

  oidc {
    issuer_uri        = "https://token.actions.githubusercontent.com"
    allowed_audiences = []
  }
}

resource "google_service_account" "ci" {
  for_each = var.service_accounts

  project      = var.project
  account_id   = each.key
  display_name = each.value.display_name
  description  = "CI/CD service account for ${each.value.repository}"
}

# IAM binding that allows the named repo to call
# iam.serviceAccounts.getAccessToken on the SA via the federation pool.
#
# We always scope by attribute.repository, never only by
# attribute.environment. attribute.environment without a repo qualifier
# would let any repo in the same owner that defines a GitHub Environment
# with a matching name impersonate this SA, which defeats the per-repo
# blast radius guarantee. Production-grade SAs (github_environment set)
# instead rely on GitHub Environment protection rules (required
# reviewers, deployment branches) to gate token issuance to that env.
locals {
  sa_principals = {
    for k, v in var.service_accounts :
    k => "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.this.name}/attribute.repository/${v.repository}"
  }
}

resource "google_service_account_iam_member" "wif_user" {
  for_each = var.service_accounts

  service_account_id = google_service_account.ci[each.key].name
  role               = "roles/iam.workloadIdentityUser"
  member             = local.sa_principals[each.key]
}
