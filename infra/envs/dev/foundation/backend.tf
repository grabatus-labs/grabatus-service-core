# State backend for the dev environment's foundation stack.
#
# The bucket itself is created by hand (see infra/BOOTSTRAP.md) — it
# has to exist before Terraform can write state into it.
#
# Prefix convention: gbt-{env}-{component}/{stack}. The component
# segment isolates this stack from any other state living in the
# same bucket (e.g., the forecasting worker stack uses prefix
# gbt-dev-forecasting/worker).

terraform {
  backend "gcs" {
    bucket = "gbt-tfstate-dev"
    prefix = "gbt-dev-service-core/foundation"
  }
}
