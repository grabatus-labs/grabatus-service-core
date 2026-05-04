# State backend for the staging environment's foundation stack.
# Bucket created manually per infra/BOOTSTRAP.md.

terraform {
  backend "gcs" {
    bucket = "gbt-tfstate-staging"
    prefix = "gbt-staging-service-core/foundation"
  }
}
