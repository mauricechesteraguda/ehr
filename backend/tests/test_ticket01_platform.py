"""type-10042026-Maurice: Ticket01 offline platform validation RED baseline."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import pytest

from backend.users.tracing import trace_function


ROOT = Path(__file__).resolve().parents[2]
CSV = ROOT / "docs/test-cases/ehr-devsecops-platform.csv"
MANIFEST = ROOT / "platform/tool-versions.json"
TARGETS = ROOT / "platform/validation-targets.json"


@trace_function
def _ticket01_rows() -> list[dict[str, str]]:
    """type-10042026-Maurice: Read only the canonical Ticket01 rows."""
    with CSV.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    return [row for row in rows if row["Module / Feature"].startswith("Ticket 01")]


@trace_function
def _read_json(path: Path) -> dict[str, object]:
    """type-10042026-Maurice: Load a JSON contract without exposing its contents in traces."""
    return json.loads(path.read_text(encoding="utf-8"))


@trace_function
def test_TC_PLAT_0001_repository_contract_inventory() -> None:
    """TC-PLAT-0001: the offline platform contract inventory is complete and linked."""
    rows = _ticket01_rows()
    assert [row["Test Case ID"] for row in rows] == [
        "TC-PLAT-0001",
        "TC-PLAT-0002",
        "TC-PLAT-0003",
        "TC-PLAT-0004",
    ]
    manifest = _read_json(MANIFEST)
    targets = _read_json(TARGETS)
    assert manifest["schema"] == "ehr.platform.tool-versions.v1"
    assert targets["schema"] == "ehr.platform.validation-targets.v1"
    assert set(manifest["contract_inventory"]) == {"delivery", "infrastructure", "policy", "observability", "operations"}
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert all(pattern in ignore for pattern in ("*.tfstate", "*.tfplan", "kubeconfig", "platform/generated/", "credentials.json"))
    assert all(row["Automated Test Ref."] for row in rows)


@trace_function
def test_TC_PLAT_0002_offline_static_validation_without_credentials() -> None:
    """TC-PLAT-0002: validation is deterministic and does not require cloud credentials."""
    assert not any(name in os.environ for name in ("AWS_ACCESS_KEY_ID", "GOOGLE_APPLICATION_CREDENTIALS", "AZURE_CLIENT_SECRET"))
    manifest = _read_json(MANIFEST)
    targets = _read_json(TARGETS)
    assert manifest["credential_mode"] == "none"
    assert targets["offline_only"] is True
    assert set(targets["targets"]) >= {"csv-integrity", "tool-version-manifest", "credential-boundary"}
    assert all(item["pin_type"] in {"exact", "bounded"} for item in manifest["tool_versions"].values())
    assert all((item.get("version") if item["pin_type"] == "exact" else item.get("constraint")) for item in manifest["tool_versions"].values())


@trace_function
def test_TC_PLAT_0003_static_validator_malformed_input() -> None:
    """TC-PLAT-0003: malformed manifest input is rejected with a safe category."""
    from backend.users.platform_validation import validate_manifest_text

    with pytest.raises(ValueError, match="invalid_manifest"):
        validate_manifest_text('{"schema":')


@trace_function
def test_TC_PLAT_0004_static_validation_empty_no_results() -> None:
    """TC-PLAT-0004: an empty change set produces explicit machine-readable evidence."""
    from backend.users.platform_validation import validate_changed_paths

    assert validate_changed_paths([]) == {
        "status": "no_applicable_changes",
        "deployment": "not_claimed",
    }
