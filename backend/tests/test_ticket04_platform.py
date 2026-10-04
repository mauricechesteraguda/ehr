"""type-10042026-Maurice: Ticket04 GitOps/platform contracts, RED first."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
GITOPS = ROOT / "platform" / "gitops"


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _yaml(relative: str) -> dict:
    return yaml.safe_load(_read(relative))


def test_TC_PLAT_0019_environment_isolation() -> None:
    project = _yaml("platform/gitops/project.yaml")
    destinations = {item["namespace"] for item in project["spec"]["destinations"]}
    assert {"ehr-demo", "ehr-k3s", "ehr-development", "ehr-staging", "ehr-production"} <= destinations
    assert len({item for item in destinations if item.startswith("ehr-") and item != "ehr-platform"}) == 5


def test_TC_PLAT_0020_app_of_apps_order_and_references() -> None:
    root = _yaml("platform/gitops/root-application.yaml")
    assert root["spec"]["source"]["path"] == "platform/gitops/apps"
    assert root["metadata"]["annotations"]["argocd.argoproj.io/sync-options"] == "Prune=false"
    apps = list((GITOPS / "apps").glob("*.yaml"))
    assert apps
    assert all("kind: Application" in _read(str(path.relative_to(ROOT))) for path in apps if "kind: Application" in _read(str(path.relative_to(ROOT))))


def test_TC_PLAT_0021_sync_modes_and_drift() -> None:
    dev = _yaml("platform/gitops/apps/ehr-development.yaml")
    prod = _yaml("platform/gitops/apps/ehr-production.yaml")
    assert "automated" in dev["spec"]["syncPolicy"]
    assert "automated" not in prod["spec"].get("syncPolicy", {})
    assert prod["metadata"]["annotations"]["ehr.example/sync-gate"] == "approved-release"


def test_TC_PLAT_0022_helm_library_and_ehr_chart_are_referenced() -> None:
    chart = _read("platform/helm/ehr/Chart.yaml")
    assert "ehr-library" in chart
    assert "platform/helm/ehr" in _read("platform/gitops/apps/ehr-development.yaml")


def test_TC_PLAT_0023_ehr_composition_is_a_child_application() -> None:
    names = {_yaml(f"platform/gitops/apps/{name}")["metadata"]["name"] for name in ("ehr-demo.yaml", "ehr-k3s.yaml", "ehr-development.yaml", "ehr-staging.yaml", "ehr-production.yaml")}
    assert names == {"ehr-demo", "ehr-k3s", "ehr-development", "ehr-staging", "ehr-production"}


def test_TC_PLAT_0024_bootstrap_chart_has_schema_and_no_secret_values() -> None:
    assert (ROOT / "platform/helm/bootstrap/values.schema.json").exists()
    values = _read("platform/helm/bootstrap/values.yaml")
    assert "password" not in values.lower()
    assert "secret" not in values.lower()


def test_TC_PLAT_0025_migration_pre_sync_and_rollback_boundary() -> None:
    text = _read("platform/helm/ehr/templates/migration-job.yaml")
    assert "PreSync" in text
    assert "irreversible" in _read("platform/gitops/README.md").lower()


def test_TC_PLAT_0026_migration_rollback_is_not_automatic() -> None:
    text = _read("platform/gitops/README.md").lower()
    assert "recovery" in text and "does not claim to reverse" in text


def test_TC_PLAT_0027_safe_rollout_contract() -> None:
    text = _read("platform/helm/ehr/values.yaml")
    assert all(value in text for value in ("resources:", "terminationGracePeriodSeconds", "pdb:", "probes:"))


def test_TC_PLAT_0028_target_profiles_are_explicit() -> None:
    for target in ("kind", "k3s", "development", "staging", "production"):
        assert target in _read("platform/gitops/targets.yaml")


def test_TC_PLAT_0058_drift_is_reconciled_from_reviewed_git() -> None:
    root = _yaml("platform/gitops/root-application.yaml")
    assert root["spec"]["source"]["targetRevision"] == "main"
    assert root["spec"]["destination"]["server"] == "https://kubernetes.default.svc"


def test_TC_PLAT_0058_root_owns_only_gitops() -> None:
    root = _yaml("platform/gitops/root-application.yaml")
    assert root["spec"]["source"]["repoURL"] == "https://github.com/example/ehr.git"
    assert "kubectl" not in _read("platform/gitops/root-application.yaml")
