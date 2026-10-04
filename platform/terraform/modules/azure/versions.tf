// type-10042026-Maurice: AzureRM resource names follow the current provider registry.
terraform {
  required_version = ">= 1.9.8, < 2.0.0"
  required_providers {
    azurerm = {
      source = "hashicorp/azurerm", version = "~> 4.15"
    }
    helm = {
      source = "hashicorp/helm", version = "= 2.17.0"
    }
  }
}
