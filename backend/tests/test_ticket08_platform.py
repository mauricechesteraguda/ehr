"""type-10042026-Maurice: Ticket08 documentation and evidence contracts."""

import csv
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CSV = ROOT / "docs/test-cases/ehr-devsecops-platform.csv"


def _read(relative: str) -> str:
    """type-10042026-Maurice: Read a documentation contract without logging content."""
    return (ROOT / relative).read_text(encoding="utf-8")


def test_TC_PLAT_0055_documentation_diagrams_and_adrs() -> None:
    """type-10042026-Maurice: Architecture boundaries and every ADR link resolve."""
    index = _read("platform/docs/decisions/README.md")
    platform = _read("platform/README.md")
    assert "```mermaid" in index and "```mermaid" in platform
    for term in ("GitHub", "Terraform", "Argo", "workload", "data", "secret", "telemetry", "private"):
        assert term.lower() in (index + platform).lower()
    links = re.findall(r"\]\((adr-[^)]+\.md)\)", index)
    assert links and all((ROOT / "platform/docs/decisions" / link).is_file() for link in links)


def test_TC_PLAT_0056_not_deployed_url_boundary() -> None:
    """type-10042026-Maurice: Every operator README marks the reference URL as non-live."""
    readmes = [
        path for path in ROOT.rglob("README.md")
        if "node_modules" not in path.parts
        and not any(part.startswith(".") for part in path.relative_to(ROOT).parts)
    ]
    assert readmes
    marker = "Live URL: Not deployed"
    for path in readmes:
        text = path.read_text(encoding="utf-8")
        assert marker in text, path
        assert "reference configuration only" in text.lower(), path


def test_TC_PLAT_0057_current_application_regression() -> None:
    """type-10042026-Maurice: Existing regression gates remain documented and discoverable."""
    root = _read("README.md")
    assert "npm test -- --run" in root
    assert "python3 -m pytest" in root or "pytest -q" in root
    assert "docker compose" in root and "validate:evidence" in root
    assert not any("skip" in line.lower() and "test" in line.lower() for line in root.splitlines())


def test_TC_PLAT_0059_acceptance_evidence_classification() -> None:
    """type-10042026-Maurice: Canonical CSV is complete and classifies unvalidated claims."""
    with CSV.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
        fields = rows[0].keys()
    assert len(fields) == 18
    assert [row["Test Case ID"] for row in rows] == [f"TC-PLAT-{number:04d}" for number in range(1, 60)]
    assert all(row["Requirement ID"].strip() for row in rows)
    assert all(row["Status (Pass/Fail)"].strip() == "Not Run" for row in rows)
    assert all(row["Automated Test Ref."].strip() for row in rows)
    docs = _read("platform/README.md").lower()
    for evidence_class in ("static", "kind", "k3s", "cloud", "not run"):
        assert evidence_class in docs
    assert "unvalidated" in docs
