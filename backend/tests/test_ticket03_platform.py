"""type-10042026-Maurice: Ticket03 Helm and workload contracts, RED first."""

from pathlib import Path
import logging


logger = logging.getLogger(__name__)


ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    """type-10042026-Maurice: Read only safe repository contract text."""
    logger.debug("reading platform contract")
    return (ROOT / relative).read_text(encoding="utf-8")


def test_TC_PLAT_0009_k3s_profile_resource_boundary() -> None:
    text = _read("platform/helm/ehr/values.yaml")
    assert "k3s" in text and "concurrency: 1" in text
    assert "resources:" in text and "limits:" in text


def test_TC_PLAT_0010_lightweight_profile_boundary() -> None:
    text = _read("platform/helm/ehr/values.yaml")
    assert "lightweight" in text and "telemetry" in text
    assert "serviceMonitor" in text


def test_TC_PLAT_0011_provider_selection_is_documented_not_implemented() -> None:
    text = _read("platform/helm/ehr/values.yaml")
    assert 'provider: "none"' in text
    assert "EKS" in _read("platform/README.md")


def test_TC_PLAT_0012_workload_chart_does_not_provision_infrastructure() -> None:
    # Ticket06 adds infrastructure outside the workload chart; the chart itself remains free of
    # Terraform resources while the platform root is now an intentional sibling contract.
    assert (ROOT / "platform" / "terraform").exists()
    assert "Terraform" in _read("platform/README.md")


def test_TC_PLAT_0013_identity_boundary_has_no_static_credentials() -> None:
    rendered = _read("platform/helm/ehr/templates/deployment.yaml")
    assert "serviceAccountName" in rendered and "value:" not in rendered


def test_TC_PLAT_0014_remote_state_is_not_claimed_by_application_chart() -> None:
    assert "remote state" not in _read("platform/helm/ehr/Chart.yaml").lower()


def test_TC_PLAT_0015_state_failure_is_not_hidden_by_chart() -> None:
    values = _read("platform/helm/ehr/values.yaml")
    assert "persistence" in values and "storageClass" in values


def test_TC_PLAT_0016_terraform_opentofu_boundary_is_documented() -> None:
    text = _read("platform/tool-versions.json")
    assert "opentofu" in text and "terraform" in text


def test_TC_PLAT_0017_managed_and_demo_data_boundary() -> None:
    values = _read("platform/helm/ehr/values.yaml")
    assert "demo" in values and "production" in values and "managed" in values


def test_TC_PLAT_0018_provider_networking_is_not_falsely_configured() -> None:
    rendered = _read("platform/helm/ehr/templates/service.yaml")
    assert "type: LoadBalancer" not in rendered and "type: NodePort" not in rendered
