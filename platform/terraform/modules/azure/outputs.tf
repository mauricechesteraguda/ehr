// type-10042026-Maurice: integration handles are sensitive where they identify private services.
output "cluster" {
  value = {
    name = azurerm_kubernetes_cluster.this.name, fqdn = azurerm_kubernetes_cluster.this.private_fqdn, oidc_issuer = azurerm_kubernetes_cluster.this.oidc_issuer_url
  }
  sensitive = true
}
output "registry" {
  value = {
    login_server = azurerm_container_registry.app.login_server
  }
  sensitive = false
}
output "secret_store" {
  value = {
    vault_uri = azurerm_key_vault.this.vault_uri, vault_id = azurerm_key_vault.this.id
  }
  sensitive = true
}
output "database" {
  value = {
    fqdn = azurerm_postgresql_flexible_server.postgres.fqdn, administrator_login = azurerm_postgresql_flexible_server.postgres.administrator_login
  }
  sensitive = true
}
output "redis" {
  value = {
    hostname = azurerm_managed_redis.redis.hostname, port = azurerm_managed_redis.redis.default_database[0].port
  }
  sensitive = true
}
output "shared_file_storage" {
  value = {
    storage_account = azurerm_storage_account.shared.name, share = azurerm_storage_share.exports.name, private_endpoint = azurerm_private_endpoint.storage.private_service_connection[0].private_ip_address
  }
  sensitive = true
}
output "dns_lb_integration" {
  value = {
    domain = var.domain_name, private_dns_zone = azurerm_private_dns_zone.postgres.name
  }
  sensitive = true
}
output "workload_identity" {
  value = {
    client_id = azurerm_user_assigned_identity.aks.client_id, oidc_issuer = azurerm_kubernetes_cluster.this.oidc_issuer_url
  }
  sensitive = true
}
output "argo_bootstrap" {
  value = {
    enabled = var.bootstrap_argo, release = var.bootstrap_argo ? helm_release.argo[0].name : null
  }
}
