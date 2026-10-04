// type-10042026-Maurice: provider pins are reviewed centrally per module.
terraform {
  required_version = ">= 1.9.8, < 2.0.0"
  required_providers {
    aws = {
      source = "hashicorp/aws", version = "~> 5.70"
    }
    helm = {
      source = "hashicorp/helm", version = "= 2.17.0"
    }
    tls = {
      source = "hashicorp/tls", version = "~> 4.0"
    }

  }
}
