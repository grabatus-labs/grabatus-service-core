# `infra/` — Terraform Infrastructure-as-Code

Lives the GCP infrastructure for `grabatus-service-core` across three
environments (`dev`, `staging`, `production`). The companion stacks for
the forecasting worker live in `services/grabatus-forecasting/infra/`.

## Layout

```
infra/
├── BOOTSTRAP.md           # one-time gcloud commands for state buckets
├── modules/               # reusable Terraform modules (Plan 2D / CP2-CP5)
│   ├── wif/                       # GitHub Actions ↔ GCP federation
│   ├── artifact_registry/         # Docker repo + IAM bindings
│   ├── shared_receiver/           # Cloud Run Service for the receiver
│   └── alerts_common/             # cross-cutting monitoring policies
└── envs/                  # one root stack per environment
    ├── dev/foundation/
    ├── staging/foundation/
    └── production/foundation/
```

## Quick reference

```bash
# Per env, from infra/envs/<env>/foundation:
terraform fmt -check -recursive ../../..
terraform init                                  # needs the GCS bucket
terraform plan -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars
```

For a no-credentials syntax check (useful in CI before any apply):

```bash
terraform init -backend=false
terraform validate
```

## Spec / plan

* Design: `docs/superpowers/specs/2026-04-27-plano-2-forecasting-refactor-design.md`
  (sections 8.1–8.11)
* Plan: `services/grabatus-forecasting/docs/superpowers/plans/2026-05-01-2D-iac-foundation.md`

The plan lives in the forecasting repo because it spans both repos and
sits next to its companion (Plan 2C). Every checkpoint marks the repo
it touches.
