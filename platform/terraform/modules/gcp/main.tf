// type-10042026-Maurice: private regional GKE and managed data services.
provider "google" {
  project               = var.project_id
  region                = var.region
  user_project_override = true
  default_labels = merge(var.labels, {
    environment = var.environment, managed_by = "terraform"
  })
}
resource "google_kms_key_ring" "platform" {
  name     = "${var.name}-ring"
  location = var.region
}
resource "google_kms_crypto_key" "platform" {
  name            = "${var.name}-key"
  key_ring        = google_kms_key_ring.platform.id
  rotation_period = "7776000s"
}
resource "google_compute_network" "this" {
  name                    = var.name
  auto_create_subnetworks = false
}
resource "google_compute_subnetwork" "nodes" {
  name                     = "${var.name}-nodes"
  region                   = var.region
  network                  = google_compute_network.this.id
  ip_cidr_range            = var.network_cidr
  private_ip_google_access = true
  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = var.pods_cidr
  }
  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = var.services_cidr
  }
}
resource "google_compute_router" "this" {
  name    = "${var.name}-router"
  region  = var.region
  network = google_compute_network.this.id
}
resource "google_compute_router_nat" "this" {
  name                               = "${var.name}-nat"
  router                             = google_compute_router.this.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "LIST_OF_SUBNETWORKS"
  subnetwork {
    name                    = google_compute_subnetwork.nodes.id
    source_ip_ranges_to_nat = ["ALL_IP_RANGES"]
  }
}
resource "google_container_cluster" "this" {
  name                     = var.name
  location                 = var.region
  network                  = google_compute_network.this.name
  subnetwork               = google_compute_subnetwork.nodes.name
  min_master_version       = var.kubernetes_version
  remove_default_node_pool = true
  initial_node_count       = 1
  networking_mode          = "VPC_NATIVE"
  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }
  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = true
    master_ipv4_cidr_block  = "172.16.0.0/28"
  }
  master_authorized_networks_config {
    cidr_blocks {
      cidr_block   = var.network_cidr
      display_name = "private-vpc"
    }
  }
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }
  logging_config {
    enable_components = ["SYSTEM_COMPONENTS", "WORKLOADS"]
  }
  monitoring_config {
    enable_components = ["SYSTEM_COMPONENTS", "WORKLOADS"]
  }
  database_encryption {
    state    = "ENCRYPTED"
    key_name = google_kms_crypto_key.platform.id
  }
}
resource "google_container_node_pool" "this" {
  name       = "${var.name}-nodes"
  location   = var.region
  cluster    = google_container_cluster.this.name
  node_count = var.node_count
  node_config {
    machine_type = var.environment == "production" ? "e2-standard-4" : "e2-standard-2"
    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    metadata = {
      "disable-legacy-endpoints" = "true"
    }
    workload_metadata_config {
      mode = "GKE_METADATA"
    }
    shielded_instance_config {
      enable_secure_boot = true
    }
  }
}
resource "google_artifact_registry_repository" "app" {
  location      = var.region
  repository_id = var.name
  format        = "DOCKER"
  kms_key_name  = google_kms_crypto_key.platform.id
}
resource "google_sql_database_instance" "postgres" {
  name                = "${var.name}-postgres"
  database_version    = "POSTGRES_16"
  region              = var.region
  deletion_protection = var.environment == "production"
  settings {
    tier              = var.environment == "production" ? "db-custom-4-16384" : "db-custom-2-8192"
    availability_type = "REGIONAL"
    disk_type         = "PD_SSD"
    disk_size         = 100
    disk_autoresize   = true
    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = var.environment == "production" ? 7 : 3
      backup_retention_settings {
        retained_backups = var.environment == "production" ? 35 : 7
      }
    }
    ip_configuration {
      ipv4_enabled                                  = false
      private_network                               = google_compute_network.this.id
      enable_private_path_for_google_cloud_services = true
      ssl_mode                                      = "ENCRYPTED_ONLY"
    }
  }
}
resource "google_redis_instance" "redis" {
  name                    = var.name
  tier                    = "STANDARD_HA"
  memory_size_gb          = var.environment == "production" ? 5 : 1
  region                  = var.region
  authorized_network      = google_compute_network.this.id
  connect_mode            = "PRIVATE_SERVICE_ACCESS"
  transit_encryption_mode = "SERVER_AUTHENTICATION"
  auth_enabled            = true
  customer_managed_key    = google_kms_crypto_key.platform.id
}
resource "google_filestore_instance" "shared" {
  name = var.name
  tier = var.environment == "production" ? "BASIC_HDD" : "BASIC_SSD"
  zone = var.zones[0]
  file_shares {
    name        = "exports"
    capacity_gb = var.environment == "production" ? 1024 : 128
  }
  networks {
    network = google_compute_network.this.name
    modes   = ["MODE_IPV4"]
  }
}
resource "google_secret_manager_secret" "platform" {
  secret_id = "${var.name}-platform"
  replication {
    auto {}
  }
}
resource "google_dns_managed_zone" "this" {
  count      = var.domain_name == null ? 0 : 1
  name       = replace(var.name, "-", "")
  dns_name   = "${var.domain_name}."
  visibility = "private"
  private_visibility_config {
    networks {
      network_url = google_compute_network.this.id
    }
  }
}
resource "google_service_account" "workload" {
  account_id   = substr(replace(var.name, "-", ""), 0, 30)
  display_name = "${var.name} workload identity"
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
  depends_on = [google_container_node_pool.this]
}
