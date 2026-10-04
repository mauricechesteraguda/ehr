// type-10042026-Maurice: isolated gcp/development root; provider identity is ambient/OIDC only.
terraform {
  required_version = ">= 1.9.8, < 2.0.0"
  backend "gcs" {
    prefix = "ehr/gcp/development"
  }
}
provider "google" {
  project = var.project_id
  region  = var.region
}
provider "helm" {
  kubernetes {
    host = "https://${module.platform.cluster.endpoint}"
    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "gke-gcloud-auth-plugin"
    }
  }
}
module "platform" {
  source             = "../../../modules/gcp"
  name               = var.name
  project_id         = var.project_id
  environment        = var.environment
  region             = var.region
  zones              = var.zones
  kubernetes_version = var.kubernetes_version
  bootstrap_argo     = var.bootstrap_argo
}
