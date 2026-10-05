// type-10042026-Maurice: isolated azure/production root;provider identity is ambient/OIDC only.
terraform {
  required_version = ">= 1.9.8, < 2.0.0"
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 4.15" }
    helm    = { source = "hashicorp/helm", version = "= 2.17.0" }
  }
  backend "azurerm" {
    key = "ehr/azure/production/terraform.tfstate"
  }
}
provider "azurerm" {
  features {}
}
provider "helm" {
  kubernetes {
    host = "https://${module.platform.cluster.fqdn}"
    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "kubelogin"
      args        = ["get-token", "--login", "azurecli"]
    }
  }
}
module "platform" {
  source                  = "../../../modules/azure"
  name                    = var.name
  environment             = var.environment
  location                = var.location
  kubernetes_version      = var.kubernetes_version
  postgres_admin_password = var.postgres_admin_password
  bootstrap_argo          = var.bootstrap_argo
}
