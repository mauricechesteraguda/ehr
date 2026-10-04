// type-10042026-Maurice: handles only;Terraform never returns secret payloads.
output "cluster" {
  value = {
    name = google_container_cluster.this.name, endpoint = google_container_cluster.this.endpoint, workload_pool = "${var.project_id}.svc.id.goog"
  }
  sensitive = true
}
output "registry" {
  value = {
    repository = google_artifact_registry_repository.app.name, url = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.app.repository_id}"
  }
}
output "secret_store" {
  value = {
    secret_id = google_secret_manager_secret.platform.id, kms_key = google_kms_crypto_key.platform.id
  }
  sensitive = true
}
output "database" {
  value = {
    address = google_sql_database_instance.postgres.private_ip_address, connection_name = google_sql_database_instance.postgres.connection_name, secret_id = google_secret_manager_secret.platform.id
  }
  sensitive = true
}
output "redis" {
  value = {
    host = google_redis_instance.redis.host, port = google_redis_instance.redis.port
  }
  sensitive = true
}
output "shared_file_storage" {
  value = {
    name = google_filestore_instance.shared.name, ip = google_filestore_instance.shared.networks[0].ip_addresses[0]
  }
  sensitive = true
}
output "dns_lb_integration" {
  value = {
    managed_zone = var.domain_name == null ? null : google_dns_managed_zone.this[0].name, domain = var.domain_name
  }
  sensitive = true
}
output "workload_identity" {
  value = {
    google_service_account = google_service_account.workload.email, workload_pool = "${var.project_id}.svc.id.goog"
  }
  sensitive = true
}
output "argo_bootstrap" {
  value = {
    enabled = var.bootstrap_argo, release = var.bootstrap_argo ? helm_release.argo[0].name : null
  }
}
