// type-10042026-Maurice: isolated aws/development root; provider identity is ambient/OIDC only.
terraform {
  required_version = ">= 1.9.8, < 2.0.0"
  required_providers {
    aws  = { source = "hashicorp/aws", version = "~> 5.70" }
    helm = { source = "hashicorp/helm", version = "= 2.17.0" }
  }
  backend "s3" {
    key = "ehr/aws/development/terraform.tfstate"
  }
}
provider "aws" {
  region = var.region
}
provider "helm" {
  kubernetes {
    host                   = module.platform.cluster.endpoint
    cluster_ca_certificate = base64decode(module.platform.cluster.certificate_authority_data)
    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", module.platform.cluster.name, "--region", var.region]
    }
  }
}
module "platform" {
  source                = "../../../modules/aws"
  name                  = var.name
  environment           = var.environment
  region                = var.region
  kubernetes_version    = var.kubernetes_version
  availability_zones    = var.availability_zones
  private_subnet_cidrs  = var.private_subnet_cidrs
  public_subnet_cidrs   = var.public_subnet_cidrs
  database_subnet_cidrs = var.database_subnet_cidrs
  admin_cidrs           = var.admin_cidrs
  bootstrap_argo        = var.bootstrap_argo
}
