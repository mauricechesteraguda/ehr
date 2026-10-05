"""type-10042026-Maurice: Ticket07 CI/supply-chain contract tests, one CSV case each."""

import ast
import json
import logging
import re
import shlex
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github/workflows"
LOGGER = logging.getLogger(__name__)


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


def test_TC_PLAT_0060_workflow_dependency_requirement_paths() -> None:
    """type-10052026-Maurice: CI dependency files resolve from each run directory."""
    LOGGER.debug("dependency requirement validation entered")
    try:
        data = yaml.safe_load(_text("platform-validation.yml"))
        workflow_defaults = data.get("defaults", {}).get("run", {})
        found = False
        for job in data.get("jobs", {}).values():
            job_defaults = job.get("defaults", {}).get("run", {})
            for step in job.get("steps", []):
                command = step.get("run")
                if not command:
                    continue
                tokens = []
                for line in command.splitlines():
                    tokens.extend(shlex.split(line, comments=True))
                if ["pip", "install"] not in [tokens[index:index + 2] for index in range(len(tokens) - 1)]:
                    continue
                install_at = next(index for index in range(len(tokens) - 1) if tokens[index:index + 2] == ["pip", "install"])
                working_directory = step.get(
                    "working-directory",
                    job_defaults.get("working-directory", workflow_defaults.get("working-directory", ".")),
                )
                base = Path(working_directory)
                base = base if base.is_absolute() else ROOT / base
                for token_index in range(install_at + 2, len(tokens)):
                    token = tokens[token_index]
                    requirement = None
                    if token in ("-r", "--requirement") and token_index + 1 < len(tokens):
                        requirement = tokens[token_index + 1]
                    elif token.startswith("--requirement="):
                        requirement = token.split("=", 1)[1]
                    elif token.startswith("-r") and token != "-r":
                        requirement = token[2:]
                    if requirement:
                        found = True
                        assert (base / requirement).is_file(), requirement
        assert found
    except AssertionError:
        LOGGER.debug("dependency requirement validation failed")
        raise
    except Exception:
        LOGGER.debug("dependency requirement validation raised an exception")
        raise
    finally:
        LOGGER.debug("dependency requirement validation exited")


def test_TC_PLAT_0061_platform_collection_imports_are_declared() -> None:
    """type-10052026-Maurice: collection imports must be installable from root requirements."""
    workflow = _text("platform-validation.yml")
    test_paths = re.findall(r"backend/tests/test_ticket\d+_(?:platform|terraform)\.py", workflow)
    assert test_paths

    stdlib = set(sys.stdlib_module_names)
    imported = set()
    for relative in test_paths:
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"), filename=relative)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.add(node.module.split(".", 1)[0])

    third_party = imported - stdlib - {"backend"}
    declared = {
        line.split("[", 1)[0].split("=", 1)[0].split(">", 1)[0].split("<", 1)[0].strip().lower()
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    module_to_distribution = {"yaml": "pyyaml", "pytest": "pytest"}
    assert third_party <= module_to_distribution.keys()
    assert {module_to_distribution[module] for module in third_party} <= declared


def test_TC_PLAT_0062_postgres_service_matches_django_ci_environment() -> None:
    """type-10052026-Maurice: PostgreSQL-backed CI tests have an isolated ready service."""
    data = yaml.safe_load(_text("platform-validation.yml"))
    jobs = data.get("jobs", {})
    matching = [
        job for job in jobs.values()
        if any("backend/tests/test_ticket07.py" in (step.get("run") or "") for step in job.get("steps", []))
    ]
    assert matching, "a job running test_ticket07.py must be discoverable"
    assert len(matching) == 1
    job = matching[0]
    services = job.get("services", {})
    assert set(services) == {"postgres"}, "the Django CI job must not provision Redis"
    postgres = services["postgres"]
    assert re.fullmatch(r"postgres:17\.2-alpine@sha256:[0-9a-f]{64}", postgres["image"])
    assert postgres["ports"] == ["5432:5432"]

    run_id = "${{ github.run_id }}"
    attempt = "${{ github.run_attempt }}"
    expected = {
        "POSTGRES_DB": f"ehr_ci_{run_id}_{attempt}",
        "POSTGRES_USER": f"ehr_ci_{run_id}_{attempt}",
        "POSTGRES_PASSWORD": f"ci_only_{run_id}_{attempt}",
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": 5432,
    }
    assert postgres["env"] == {key: expected[key] for key in ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD")}
    assert job["env"] == expected | {"DJANGO_SECRET_KEY": f"ci-only-{run_id}-{attempt}"}

    options = postgres.get("options", "")
    assert re.search(r'--health-cmd[= ]+"?pg_isready\s+-U\s+\$?\{?POSTGRES_USER\}?\s+-d\s+\$?\{?POSTGRES_DB\}?', options)
    for option, maximum in (("--health-interval", 30), ("--health-timeout", 30), ("--health-retries", 30)):
        match = re.search(rf"{option}\s+(\d+)(?:s)?", options)
        assert match and 0 < int(match.group(1)) <= maximum
    steps = job["steps"]
    readiness = next(i for i, step in enumerate(steps) if "pg_isready" in (step.get("run") or ""))
    tests = next(i for i, step in enumerate(steps) if "backend/tests/test_ticket07.py" in (step.get("run") or ""))
    assert readiness < tests
