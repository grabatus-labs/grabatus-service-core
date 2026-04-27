# ADR-0006 — Workload Identity Federation for GitHub → GCP

- **Status:** Accepted
- **Date:** 2026-04-26

## Context

GitHub Actions workflows need to deploy to Cloud Run, push to Artifact Registry, and run real-GCP integration tests. The traditional approach is to store a GCP service account JSON key in GitHub Secrets.

This is a security risk:

1. The key is **long-lived**. Rotation is manual and frequently skipped.
2. Anyone with repository write access can extract the key from logs (despite secret masking, exfiltration paths exist).
3. A leaked key grants the same permissions for as long as it stays valid, with limited revocation telemetry.

## Decision

We use **Workload Identity Federation (WIF)**. GitHub's OIDC token is exchanged for a short-lived GCP access token via a configured workload identity pool, scoped to the `grabatus/grabatus-service-core` repository and to specific workflow files.

No GCP service account JSON key is stored in GitHub Secrets. The CI workflows authenticate via `google-github-actions/auth@v2` with `workload_identity_provider` and `service_account` parameters.

The setup is provisioned once via Terraform under `infra/wif/` (separate repository) and yields:

- A workload identity **pool** (`gh-grabatus`)
- A workload identity **provider** (`github-actions`)
- A GCP **service account** with minimum-necessary IAM bindings (one per environment: `ci-test`, `ci-deploy`)
- An **attribute mapping** that enforces `assertion.repository == "grabatus/grabatus-service-core"`

## Alternatives Considered

- **Service account JSON in GitHub Secrets:** Rejected for the security reasons above.
- **Self-hosted runner with attached GCE service account:** Rejected — adds operational complexity and CI flakiness.
- **`gcloud auth login` per workflow:** Not viable — requires interactive consent.

## Consequences

- No long-lived credentials in GitHub. Token lifetime is one hour.
- The trust relationship is auditable in GCP (one IAM binding, one provider, one attribute mapping).
- Setup is one-time Terraform; runtime is zero-config.
- The cost is that WIF setup is unfamiliar to engineers used to JSON keys. We document the setup in `docs/security.rst` and provide a runbook in `tutorials/running_tests.rst`.
