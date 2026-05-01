# Terraform state-bucket bootstrap

This is the **only** step in the Phase 5 IaC rollout that cannot be
managed by Terraform itself: the GCS bucket that stores the Terraform
state has to exist before Terraform can write to it. Run the snippet
below once per environment, then never touch it again — every other
GCP resource lands via `terraform apply`.

The buckets created here are referenced by the `backend "gcs"` block
in `infra/envs/{env}/foundation/backend.tf`.

## Pre-requisites

* `gcloud` CLI authenticated against an account with
  `storage.admin` on the target project.
* Three GCP projects already provisioned (one per env). They are
  expected to be:

| Env | Project ID |
|---|---|
| `dev` | `grabatus-dev` |
| `staging` | `grabatus-staging` |
| `production` | `grabatus` |

If your project IDs differ, substitute them everywhere below.

## Procedure

Run **once per environment**:

```bash
ENV=dev          # or: staging, production
PROJECT=grabatus-dev   # match the table above
REGION=us-east1
BUCKET="gbt-tfstate-${ENV}"

gcloud storage buckets create "gs://${BUCKET}" \
  --project="${PROJECT}" \
  --location="${REGION}" \
  --uniform-bucket-level-access \
  --public-access-prevention

gcloud storage buckets update "gs://${BUCKET}" \
  --versioning
```

Why each flag:

* `--uniform-bucket-level-access` — disables legacy ACLs; only IAM
  governs access. This is required for the deploy SA permissions to
  work as written in the Terraform modules.
* `--public-access-prevention` — defence-in-depth. State files contain
  resource IDs and (occasionally) sensitive attributes; they must
  never be reachable from the public internet.
* `--versioning` — preserves the previous `default.tfstate` when a
  Terraform run overwrites it. Lets you recover from a corrupted
  apply or a malicious wipe by reading an older version.

## Verifying

After both buckets exist:

```bash
gcloud storage buckets describe gs://gbt-tfstate-${ENV} \
  --format="value(versioning.enabled,iamConfiguration.uniformBucketLevelAccess.enabled,iamConfiguration.publicAccessPrevention)"
# Expected: True\tTrue\tenforced
```

## Granting Terraform access

The `terraform apply` runner (a CI service account, or your own
`gcloud auth application-default login` for a manual run) needs
`roles/storage.objectAdmin` on the bucket. The role is granted by the
WIF module (Plan 2D / CP2) once the foundation stack lands.

For the very first apply (chicken-and-egg), grant `objectAdmin`
manually to the bootstrapping principal:

```bash
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member="user:you@example.com" \
  --role="roles/storage.objectAdmin"
```

Remove that binding after the foundation stack has applied for the
first time and the deploy SA has taken over.

## Idempotency

The commands above are not idempotent: a second run fails with
`AlreadyExists`. That is intentional — the bucket existence is
load-bearing infrastructure and should be created exactly once per
env. If you genuinely need to recreate one (e.g., to migrate to a
different region), restore from a versioned `tfstate` backup before
flipping the bucket name in `backend.tf`.

## Related

* The forecasting repo has a sibling document at
  `services/grabatus-forecasting/infra/BOOTSTRAP.md` that points at
  the same buckets — both repos' state lives in the same buckets,
  with different `prefix` keys per `backend.tf`.
