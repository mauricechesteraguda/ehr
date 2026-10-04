// type-10042026-Maurice: common install contract with explicit private-network inputs.
variable "name" {
  type = string
  validation {
    condition     = can(regex("^[a-z0-9-]{3,40}$", var.name))
    error_message = "name must be lowercase and 3-40 characters."
  }
}
variable "project_id" {
  type = string
  validation {
    condition     = var.project_id != ""
    error_message = "project_id is required."
  }
}
variable "environment" {
  type = string
  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "invalid environment."
  }
}
variable "region" {
  type = string
}
variable "zones" {
  type = list(string)
  validation {
    condition     = length(var.zones) >= 2
    error_message = "at least two zones are required."
  }
}
variable "kubernetes_version" {
  type = string
}
variable "network_cidr" {
  type    = string
  default = "10.52.0.0/16"
}
variable "pods_cidr" {
  type    = string
  default = "10.53.0.0/16"
}
variable "services_cidr" {
  type    = string
  default = "10.54.0.0/20"
}
variable "node_count" {
  type    = number
  default = 2
  validation {
    condition     = var.node_count >= 2
    error_message = "private regional GKE requires at least two nodes."
  }
}
variable "domain_name" {
  type     = string
  default  = null
  nullable = true
}
variable "bootstrap_argo" {
  type    = bool
  default = false
}
variable "argo_chart_version" {
  type    = string
  default = "7.7.16"
}
variable "labels" {
  type    = map(string)
  default = {}
}
