"""type-10042026-Maurice: Ticket06 Terraform RED/GREEN structural contracts.

These checks deliberately inspect source contracts only. They never initialize a cloud backend,
request credentials, plan, apply, or emit provider subprocess output.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TF = ROOT / "platform" / "terraform"


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_TC_PLAT_0012_terraform_scope_is_cluster_and_argo_only() -> None:
    text = _read("platform/terraform/README.md")
    assert "Terraform owns infrastructure" in text
    assert "Argo owns every other add-on and workload" in text


def test_TC_PLAT_0014_remote_state_is_isolated_and_locked() -> None:
    backends = list(TF.glob("environments/*/*/backend.hcl.example"))
    assert len(backends) == 9
    text = "\n".join(path.read_text(encoding="utf-8") for path in backends)
    assert "ehr/aws/development/terraform.tfstate" in text
    assert "ehr/gcp/production" in text
    assert "use_azuread_auth = true" in text


def test_TC_PLAT_0016_opentofu_compatibility_and_provider_pins() -> None:
    text = _read("platform/terraform/README.md")
    assert "Terraform 1.9.8" in text and "OpenTofu 1.8" in text
    assert all("required_version" in p.read_text(encoding="utf-8") for p in TF.glob("modules/*/versions.tf"))


def test_TC_PLAT_0018_provider_parity() -> None:
    for cloud, resource in (("aws", "aws_eks_cluster"), ("gcp", "google_container_cluster"), ("azure", "azurerm_kubernetes_cluster")):
        text = (TF / "modules" / cloud / "main.tf").read_text(encoding="utf-8")
        assert resource in text
        assert "private" in text.lower()


def test_TC_PLAT_0031_workload_identity_has_no_static_keys() -> None:
    for path in TF.glob("modules/*/*.tf"):
        text = path.read_text(encoding="utf-8").lower()
        assert "secret_access_key" not in text and "access_key =" not in text
    assert "oidc" in _read("platform/terraform/modules/aws/main.tf").lower()
    assert "workload_identity" in _read("platform/terraform/modules/gcp/main.tf")
    assert "workload_identity_enabled" in _read("platform/terraform/modules/azure/main.tf")


def test_TC_PLAT_0036_private_administration_and_data_services() -> None:
    aws = _read("platform/terraform/modules/aws/main.tf")
    gcp = _read("platform/terraform/modules/gcp/main.tf")
    azure = _read("platform/terraform/modules/azure/main.tf")
    assert "endpoint_public_access" in aws and "publicly_accessible" in aws
    assert "enable_private_endpoint" in gcp and "ipv4_enabled" in gcp
    assert "private_cluster_enabled" in azure and "public_network_access_enabled" in azure


def test_TC_PLAT_0041_encryption_backups_and_production_protection() -> None:
    for cloud in ("aws", "gcp", "azure"):
        text = (TF / "modules" / cloud / "main.tf").read_text(encoding="utf-8")
        assert "backup" in text.lower() and "production" in text
        assert "deletion_protection" in text or "deletion_protection_enabled" in text or "purge_protection_enabled" in text
        assert "kms" in text.lower() or "encryption" in text.lower()


def test_TC_PLAT_0042_managed_services_and_shared_storage() -> None:
    expected = {
        "aws": ("aws_db_instance", "aws_elasticache_replication_group", "aws_efs_file_system"),
        "gcp": ("google_sql_database_instance", "google_redis_instance", "google_filestore_instance"),
        "azure": ("azurerm_postgresql_flexible_server", "azurerm_managed_redis", "azurerm_storage_share"),
    }
    for cloud, resources in expected.items():
        text = (TF / "modules" / cloud / "main.tf").read_text(encoding="utf-8")
        assert all(resource in text for resource in resources)


def test_TC_PLAT_0043_outputs_are_secret_safe_and_common() -> None:
    names = {"cluster", "registry", "secret_store", "database", "redis", "shared_file_storage", "dns_lb_integration", "workload_identity", "argo_bootstrap"}
    for path in TF.glob("modules/*/outputs.tf"):
        text = path.read_text(encoding="utf-8")
        assert names.issubset({line.split('"')[1] for line in text.splitlines() if line.startswith("output ")})
        assert "password" not in text.lower() and "secret_value" not in text.lower()


def test_TC_PLAT_0044_argo_is_optional_and_pinned() -> None:
    for path in TF.glob("modules/*/main.tf"):
        text = path.read_text(encoding="utf-8")
        assert "bootstrap_argo" in text and 'chart            = "argo-cd"' in text
        assert "version" in text and "var.argo_chart_version" in text


def test_TC_PLAT_0045_no_credentials_or_default_secret_values() -> None:
    forbidden = ("AWS_ACCESS_KEY_ID", "client_secret", "private_key", "supplied-out-of-band", "not-configured")
    for path in TF.rglob("*.tf"):
        text = path.read_text(encoding="utf-8")
        assert not any(value in text for value in forbidden)


def test_TC_PLAT_0052_rpo_rto_limitations_are_honest() -> None:
    text = _read("platform/terraform/README.md") + _read("platform/docs/decisions/adr-009-multi-cloud-terraform.md")
    assert "RPO15m/RTO4h" in text
    assert "not measured" in text
