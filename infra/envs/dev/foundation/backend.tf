# State backend for the dev environment's foundation stack.
#
# The bucket itself is created by hand (see infra/BOOTSTRAP.md) — it
# has to exist before Terraform can write state into it.
#
# The prefix isolates this stack from any other Terraform state living
# in the same bucket (e.g., the forecasting worker stack uses prefix
# "forecasting-worker"). This avoids accidental cross-stack writes.

terraform {
  backend "gcs" {
    bucket = "gbt-tfstate-dev"
    prefix = "foundation"
  }
}
