// type-10042026-Maurice: outputs are integration handles only;secret material is never returned.
output "cluster" {
  value = {
    name = aws_eks_cluster.this.name, endpoint = aws_eks_cluster.this.endpoint, certificate_authority_data = aws_eks_cluster.this.certificate_authority[0].data, oidc_issuer = aws_eks_cluster.this.identity[0].oidc[0].issuer
  }
  sensitive = true
}
output "registry" {
  value = {
    repository_url = aws_ecr_repository.app.repository_url
  }
  sensitive = false
}
output "secret_store" {
  value = {
    secret_arn = aws_secretsmanager_secret.platform.arn, kms_key_arn = aws_kms_key.platform.arn
  }
  sensitive = true
}
output "database" {
  value = {
    address = aws_db_instance.postgres.address, port = aws_db_instance.postgres.port, secret_arn = aws_secretsmanager_secret.platform.arn
  }
  sensitive = true
}
output "redis" {
  value = {
    address = aws_elasticache_replication_group.redis.primary_endpoint_address, port = aws_elasticache_replication_group.redis.port
  }
  sensitive = true
}
output "shared_file_storage" {
  value = {
    filesystem_id = aws_efs_file_system.shared.id
  }
  sensitive = true
}
output "dns_lb_integration" {
  value = {
    hosted_zone_name = var.domain_name, cluster_security_group_id = aws_security_group.cluster.id
  }
  sensitive = true
}
output "workload_identity" {
  value = {
    oidc_provider_arn = aws_iam_openid_connect_provider.eks.arn, oidc_issuer = aws_eks_cluster.this.identity[0].oidc[0].issuer
  }
  sensitive = true
}
output "argo_bootstrap" {
  value = {
    enabled = var.bootstrap_argo, release = var.bootstrap_argo ? helm_release.argo[0].name : null
  }
  sensitive = false
}
