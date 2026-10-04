variable "name" {
  type = string
}
variable "environment" {
  type = string
}
variable "region" {
  type    = string
  default = "us-east-1"
}
variable "kubernetes_version" {
  type    = string
  default = "1.31"
}
variable "availability_zones" {
  type    = list(string)
  default = ["us-east-1a", "us-east-1b", "us-east-1c"]
}
variable "private_subnet_cidrs" {
  type    = list(string)
  default = ["10.42.1.0/24", "10.42.2.0/24", "10.42.3.0/24"]
}
variable "public_subnet_cidrs" {
  type    = list(string)
  default = ["10.42.101.0/24", "10.42.102.0/24", "10.42.103.0/24"]
}
variable "database_subnet_cidrs" {
  type    = list(string)
  default = ["10.42.201.0/24", "10.42.202.0/24", "10.42.203.0/24"]
}
variable "admin_cidrs" {
  type    = list(string)
  default = ["10.42.0.0/16"]
}
variable "bootstrap_argo" {
  type    = bool
  default = false
}
