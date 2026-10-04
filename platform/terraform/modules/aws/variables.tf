// type-10042026-Maurice: no credentials or secret values are accepted by the module.
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
    error_message = "environment must be development, staging, or production."
  }
}
variable "region" {
  type = string
}
variable "kubernetes_version" {
  type = string
  validation {
    condition     = can(regex("^[0-9]+\\.[0-9]+$", var.kubernetes_version))
    error_message = "use a Kubernetes minor version such as 1.31."
  }
}
variable "vpc_cidr" {
  type    = string
  default = "10.42.0.0/16"
}
variable "availability_zones" {
  type = list(string)
  validation {
    condition     = length(var.availability_zones) >= 2
    error_message = "at least two availability zones are required."
  }
}
variable "private_subnet_cidrs" {
  type = list(string)
}
variable "public_subnet_cidrs" {
  type = list(string)
}
variable "database_subnet_cidrs" {
  type = list(string)
}
variable "node_instance_types" {
  type    = list(string)
  default = ["m6i.large"]
}
variable "node_min_size" {
  type    = number
  default = 2
  validation {
    condition     = var.node_min_size >= 2
    error_message = "managed node groups require at least two nodes."
  }
}
variable "node_max_size" {
  type    = number
  default = 6
}
variable "admin_cidrs" {
  type = list(string)
  validation {
    condition     = length(var.admin_cidrs) > 0 && alltrue([for cidr in var.admin_cidrs : cidr != "0.0.0.0/0"])
    error_message = "cluster administration CIDRs must be explicit and non-public."
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
