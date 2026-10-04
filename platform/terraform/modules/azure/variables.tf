// type-10042026-Maurice: no client secrets or application secret values are module inputs.
variable "name" {
  type = string
  validation {
    condition     = can(regex("^[a-z0-9-]{3,40}$", var.name))
    error_message = "name must be lowercase and 3-40 characters."
  }
}
variable "environment" {
  type = string
  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "invalid environment."
  }
}
variable "location" {
  type = string
}
variable "kubernetes_version" {
  type = string
}
variable "vnet_cidr" {
  type    = string
  default = "10.62.0.0/16"
}
variable "aks_subnet_cidr" {
  type    = string
  default = "10.62.1.0/24"
}
variable "private_endpoint_subnet_cidr" {
  type    = string
  default = "10.62.2.0/24"
}
variable "zones" {
  type    = list(string)
  default = ["1", "2", "3"]
  validation {
    condition     = length(var.zones) >= 2
    error_message = "at least two availability zones are required."
  }
}
variable "node_count" {
  type    = number
  default = 2
  validation {
    condition     = var.node_count >= 2
    error_message = "AKS requires at least two nodes."
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
variable "tags" {
  type    = map(string)
  default = {}
}
variable "postgres_admin_password" {
  type      = string
  sensitive = true
  nullable  = false
  validation {
    condition     = length(var.postgres_admin_password) >= 16
    error_message = "provide the PostgreSQL password out-of-band; minimum length is 16."
  }
}
