output "cluster" {
  value     = module.platform.cluster
  sensitive = true
}
output "registry" {
  value = module.platform.registry
}
output "secret_store" {
  value     = module.platform.secret_store
  sensitive = true
}
output "database" {
  value     = module.platform.database
  sensitive = true
}
output "redis" {
  value     = module.platform.redis
  sensitive = true
}
output "shared_file_storage" {
  value     = module.platform.shared_file_storage
  sensitive = true
}
output "dns_lb_integration" {
  value     = module.platform.dns_lb_integration
  sensitive = true
}
output "workload_identity" {
  value     = module.platform.workload_identity
  sensitive = true
}
output "argo_bootstrap" {
  value = module.platform.argo_bootstrap
}
