variable "name" {
  type = string
}
variable "project_id" {
  type = string
}
variable "environment" {
  type = string
}
variable "region" {
  type    = string
  default = "us-central1"
}
variable "zones" {
  type    = list(string)
  default = ["us-central1-a", "us-central1-b", "us-central1-c"]
}
variable "kubernetes_version" {
  type    = string
  default = "1.31"
}
variable "bootstrap_argo" {
  type    = bool
  default = false
}
