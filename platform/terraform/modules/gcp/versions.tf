// type-10042026-Maurice: pinned provider family;no credentials in configuration.
terraform {
  required_version = ">= 1.9.8, < 2.0.0"
  required_providers {
    google = {
      source = "hashicorp/google", version = "~> 6.10"
    }
    helm = {
      source = "hashicorp/helm", version = "= 2.17.0"
    }
  }
}
