# State backend for the production environment's foundation stack.
# Bucket created manually per infra/BOOTSTRAP.md.

terraform {
  backend "gcs" {
    bucket = "gbt-tfstate-production"
    prefix = "foundation"
  }
}
