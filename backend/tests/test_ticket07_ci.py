"""type-10042026-Maurice: Ticket07 CI/supply-chain contract tests, one CSV case each."""

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github/workflows"


def _text(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def test_TC_PLAT_0037_ci_oidc_least_privilege() -> None:
    text = "\n".join(p.read_text(encoding="utf-8") for p in WORKFLOWS.glob("*.yml"))
    assert "id-token: write" in text and "pull_request_target" not in text
    assert all(re.search(r"uses:\s+[^\s@]+@[0-9a-f]{40}", line) for line in text.splitlines() if "uses:" in line)
    assert all(name in _text("terraform.yml") for name in ("AWS OIDC federation", "GCP OIDC federation", "Azure OIDC federation"))


def test_TC_PLAT_0038_plan_apply_approval_separation() -> None:
    data = yaml.safe_load(_text("terraform.yml"))
    text = _text("terraform.yml")
    assert data.get(True, data.get("on")) is not None  # PyYAML 1.1 parses unquoted on as true.
    assert "inputs.apply == true" in text and "inputs.confirmation == 'APPLY'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert "environment: 'terraform-${{ inputs.provider }}-${{ inputs.environment }}'" in text
    assert "retention-days: 2" in text and "head.repo.full_name == github.repository" in text


def test_TC_PLAT_0039_security_scan_threshold() -> None:
    validation, release = _text("platform-validation.yml"), _text("release.yml")
    assert "gitleaks detect" in validation and "trivy config --exit-code 1" in validation
    assert "kubeconform" in validation and "kyverno apply" in validation
    assert "trivy image --exit-code 1 --severity HIGH,CRITICAL" in release
    assert (ROOT / ".gitleaks.toml").exists() and (ROOT / "trivy.yaml").exists()


def test_TC_PLAT_0040_sbom_and_immutable_evidence() -> None:
    text = _text("release.yml")
    assert "linux/amd64,linux/arm64" in text and "spdx-json" in text and "cyclonedx-json" in text
    assert "github.sha" in text and "retention-days: 7" in text


def test_TC_PLAT_0041_cosign_keyless_verification() -> None:
    text = _text("release.yml")
    assert "cosign sign --yes" in text and "cosign attest --yes" in text
    assert "id-token: write" in text and "sha256:[0-9a-f]{64}" in text
    assert (ROOT / "policy/cosign-policy.yaml").exists()


def test_TC_PLAT_0042_multi_architecture_manifest() -> None:
    text = _text("release.yml")
    assert text.count("docker/build-push-action@") == 2
    assert text.count("linux/amd64,linux/arm64") == 2
    assert "/web:${{ github.sha }}" in text and "/api:${{ github.sha }}" in text


def test_TC_PLAT_0043_renovate_groups_without_automerge() -> None:
    data = json.loads((ROOT / ".renovaterc.json").read_text(encoding="utf-8"))
    groups = " ".join(rule["groupName"] for rule in data["packageRules"])
    assert data["automerge"] is False
    for expected in ("Actions", "Terraform", "Helm", "Container", "Security"):
        assert expected in groups


def test_TC_PLAT_0044_workflow_lint_is_deterministic() -> None:
    """type-10042026-Maurice: workflow syntax gates cannot be optional."""
    text = _text("platform-validation.yml")
    assert "actionlint" in text and "yamllint" in text
    assert re.search(r"actionlint\s+.*\.github/workflows", text)
    assert re.search(r"yamllint.*\.github/workflows|\.github/workflows.*yamllint", text)
    assert "if command -v actionlint" not in text
    assert "if command -v yamllint" not in text


def test_TC_PLAT_0045_security_tools_are_pinned_and_required() -> None:
    """type-10042026-Maurice: every core validator has a verified immutable source."""
    manifest = json.loads((ROOT / "platform/tool-versions.json").read_text(encoding="utf-8"))
    tools = manifest["tool_versions"]
    text = _text("platform-validation.yml")
    for name in ("tflint", "kubeconform", "kyverno", "gitleaks", "trivy"):
        item = tools[name]
        assert item["pin_type"] == "exact" and re.fullmatch(r"\d+\.\d+\.\d+", item["version"])
        assert item["source"].startswith("official")
        assert re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
        assert name in text and f"{name}" in text
        assert f"if command -v {name}" not in text
    assert "sha256sum --check" in text
    assert "|| true" not in text
    assert "vars.TFLINT_" not in text


def test_TC_PLAT_0046_kind_is_ci_triggered_and_scoped() -> None:
    """type-10042026-Maurice: platform changes exercise bounded disposable kind CI."""
    text = _text("kind-integration.yml")
    data = yaml.safe_load(text)
    trigger = data.get(True, data.get("on"))
    assert "workflow_dispatch" in trigger and "pull_request" in trigger
    assert "paths" in trigger["pull_request"] and "platform/**" in trigger["pull_request"]["paths"]
    assert "timeout-minutes:" in text and re.search(r"timeout-minutes:\s*\d+", text)
    assert "if: always()" in text and "kind delete cluster --name" in text
    assert "inputs.run" not in text


def test_TC_PLAT_0047_gitleaks_fixture_allowlist_is_exact() -> None:
    """type-10042026-Maurice: only named synthetic fixture lines are suppressed."""
    text = (ROOT / ".gitleaks.toml").read_text(encoding="utf-8")
    assert "test_ticket10_population_exports.py" in text
    assert "regexes" in text or "regex" in text
    assert "paths = ['''(^|/)(docs|platform/test-fixtures)/''']" not in text
    assert "api[_-]?key" not in text.lower()
    assert "allowlist" in text


def test_TC_PLAT_0048_gitleaks_generic_api_key_is_not_allowlisted() -> None:
    """type-10042026-Maurice: a nearby generic API key remains a finding."""
    text = (ROOT / ".gitleaks.toml").read_text(encoding="utf-8")
    allowed_fixture = re.findall(r"'''([^']+)'''", text)
    generic_fixture = 'api_key = "synthetic-generic-key-that-must-be-found"'
    assert not any(re.search(pattern, generic_fixture) for pattern in allowed_fixture)
