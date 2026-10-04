variable "name" {
  type = string
}
variable "environment" {
  type = string
}
variable "location" {
  type    = string
  default = "East US 2"
}
variable "kubernetes_version" {
  type    = string
  default = "1.31"
}
variable "postgres_admin_password" {
  type      = string
  sensitive = true
  nullable  = false
}
variable "bootstrap_argo" {
  type    = bool
  default = false
}
