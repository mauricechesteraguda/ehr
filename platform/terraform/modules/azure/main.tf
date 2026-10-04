// type-10042026-Maurice: private AKS, private data, managed identity, and encrypted storage.
provider "azurerm" {
  features {}
}
resource "azurerm_resource_group" "this" {
  name     = var.name
  location = var.location
  tags = merge(var.tags, {
    environment = var.environment, managed_by = "terraform"
  })
}
resource "azurerm_virtual_network" "this" {
  name                = var.name
  location            = var.location
  resource_group_name = azurerm_resource_group.this.name
  address_space       = [var.vnet_cidr]
}
resource "azurerm_subnet" "aks" {
  name                 = "aks"
  resource_group_name  = azurerm_resource_group.this.name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = [var.aks_subnet_cidr]
}
resource "azurerm_subnet" "private_endpoint" {
  name                              = "private-endpoints"
  resource_group_name               = azurerm_resource_group.this.name
  virtual_network_name              = azurerm_virtual_network.this.name
  address_prefixes                  = [var.private_endpoint_subnet_cidr]
  private_endpoint_network_policies = "Disabled"
}
resource "azurerm_public_ip" "nat" {
  name                = "${var.name}-nat"
  location            = var.location
  resource_group_name = azurerm_resource_group.this.name
  allocation_method   = "Static"
  sku                 = "Standard"
  zones               = var.zones
}
resource "azurerm_nat_gateway" "this" {
  name                = "${var.name}-nat"
  location            = var.location
  resource_group_name = azurerm_resource_group.this.name
  sku_name            = "Standard"
  zones               = var.zones
}
resource "azurerm_nat_gateway_public_ip_association" "this" {
  nat_gateway_id       = azurerm_nat_gateway.this.id
  public_ip_address_id = azurerm_public_ip.nat.id
}
resource "azurerm_subnet_nat_gateway_association" "aks" {
  subnet_id      = azurerm_subnet.aks.id
  nat_gateway_id = azurerm_nat_gateway.this.id
}
resource "azurerm_user_assigned_identity" "aks" {
  name                = "${var.name}-aks"
  location            = var.location
  resource_group_name = azurerm_resource_group.this.name
}
resource "azurerm_kubernetes_cluster" "this" {
  name                              = var.name
  location                          = var.location
  resource_group_name               = azurerm_resource_group.this.name
  dns_prefix_private_cluster        = var.name
  private_cluster_enabled           = true
  kubernetes_version                = var.kubernetes_version
  private_dns_zone_id               = "System"
  role_based_access_control_enabled = true
  oidc_issuer_enabled               = true
  workload_identity_enabled         = true
  azure_policy_enabled              = true
  default_node_pool {
    name                         = "system"
    vm_size                      = var.environment == "production" ? "Standard_D4ds_v5" : "Standard_D2ds_v5"
    node_count                   = var.node_count
    vnet_subnet_id               = azurerm_subnet.aks.id
    zones                        = var.zones
    only_critical_addons_enabled = true
  }
  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.aks.id]
  }
  network_profile {
    network_plugin      = "azure"
    network_plugin_mode = "overlay"
    network_policy      = "azure"
    outbound_type       = "userAssignedNATGateway"
  }
  oms_agent {
    log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id
  }
  key_vault_secrets_provider {
    secret_rotation_enabled = true
  }
}
resource "azurerm_log_analytics_workspace" "this" {
  name                = "${var.name}-logs"
  location            = var.location
  resource_group_name = azurerm_resource_group.this.name
  sku                 = "PerGB2018"
  retention_in_days   = var.environment == "production" ? 30 : 7
}
resource "azurerm_container_registry" "app" {
  name                          = replace(var.name, "-", "")
  resource_group_name           = azurerm_resource_group.this.name
  location                      = var.location
  sku                           = var.environment == "production" ? "Premium" : "Standard"
  admin_enabled                 = false
  public_network_access_enabled = false
  zone_redundancy_enabled       = var.environment == "production"
  encryption {
    key_vault_key_id   = azurerm_key_vault_key.registry.id
    identity_client_id = azurerm_user_assigned_identity.registry.client_id
  }
}
resource "azurerm_user_assigned_identity" "registry" {
  name                = "${var.name}-acr"
  location            = var.location
  resource_group_name = azurerm_resource_group.this.name
}
resource "azurerm_key_vault" "this" {
  name                          = substr(replace(var.name, "-", ""), 0, 24)
  location                      = var.location
  resource_group_name           = azurerm_resource_group.this.name
  tenant_id                     = data.azurerm_client_config.current.tenant_id
  sku_name                      = "standard"
  purge_protection_enabled      = var.environment == "production"
  soft_delete_retention_days    = var.environment == "production" ? 90 : 7
  public_network_access_enabled = false
  network_acls {
    default_action = "Deny"
    bypass         = "AzureServices"
  }
}
data "azurerm_client_config" "current" {}
resource "azurerm_key_vault_key" "registry" {
  name         = "${var.name}-registry"
  key_vault_id = azurerm_key_vault.this.id
  key_type     = "RSA"
  key_size     = 2048
  key_opts     = ["decrypt", "encrypt", "unwrapKey", "wrapKey"]
}
resource "azurerm_postgresql_flexible_server" "postgres" {
  name                         = "${var.name}-postgres"
  resource_group_name          = azurerm_resource_group.this.name
  location                     = var.location
  version                      = "16"
  delegated_subnet_id          = azurerm_subnet.aks.id
  private_dns_zone_id          = azurerm_private_dns_zone.postgres.id
  administrator_login          = "platformadmin"
  administrator_password       = var.postgres_admin_password
  storage_mb                   = 131072
  sku_name                     = var.environment == "production" ? "GP_Standard_D4s_v3" : "B_Standard_B1ms"
  zone                         = var.zones[0]
  backup_retention_days        = var.environment == "production" ? 35 : 7
  geo_redundant_backup_enabled = var.environment == "production"
  high_availability {
    mode                      = var.environment == "production" ? "ZoneRedundant" : "Disabled"
    standby_availability_zone = var.zones[1]
  }
  authentication {
    active_directory_auth_enabled = true
    password_auth_enabled         = false
  }
}
resource "azurerm_private_dns_zone" "postgres" {
  name                = "privatelink.postgres.database.azure.com"
  resource_group_name = azurerm_resource_group.this.name
}
resource "azurerm_private_dns_zone_virtual_network_link" "postgres" {
  name                  = var.name
  private_dns_zone_name = azurerm_private_dns_zone.postgres.name
  virtual_network_id    = azurerm_virtual_network.this.id
  resource_group_name   = azurerm_resource_group.this.name
}
resource "azurerm_managed_redis" "redis" {
  name                  = var.name
  resource_group_name   = azurerm_resource_group.this.name
  location              = var.location
  sku_name              = var.environment == "production" ? "Balanced_B5" : "Balanced_B0"
  public_network_access = "Disabled"
}
resource "azurerm_storage_account" "shared" {
  name                              = substr(replace(var.name, "-", ""), 0, 24)
  resource_group_name               = azurerm_resource_group.this.name
  location                          = var.location
  account_tier                      = "Standard"
  account_replication_type          = var.environment == "production" ? "ZRS" : "LRS"
  min_tls_version                   = "TLS1_2"
  public_network_access_enabled     = false
  infrastructure_encryption_enabled = true
  shared_access_key_enabled         = false
}
resource "azurerm_storage_share" "exports" {
  name                 = "exports"
  storage_account_name = azurerm_storage_account.shared.name
  quota                = var.environment == "production" ? 1024 : 128
  enabled_protocol     = "NFS"
}
resource "azurerm_private_endpoint" "storage" {
  name                = "${var.name}-storage"
  location            = var.location
  resource_group_name = azurerm_resource_group.this.name
  subnet_id           = azurerm_subnet.private_endpoint.id
  private_service_connection {
    name                           = var.name
    private_connection_resource_id = azurerm_storage_account.shared.id
    is_manual_connection           = false
    subresource_names              = ["file"]
  }
}
resource "helm_release" "argo" {
  count            = var.bootstrap_argo ? 1 : 0
  name             = "argocd"
  namespace        = "argocd"
  create_namespace = true
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-cd"
  version          = var.argo_chart_version
  values = [yamlencode({ server = {
    service = {
      type = "ClusterIP"
    }
    }
  })]
  depends_on = [azurerm_kubernetes_cluster.this]
}
