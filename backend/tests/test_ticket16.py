"""Ticket16 machine evidence acceptance; synthetic metadata only."""

import json
import csv
from pathlib import Path


REQUIRED = {
    "docs/accessibility-conformance-note.md": ["Manual checklist", "Known exceptions"],
    "docs/hazard-risk-register.md": ["Hazard", "Controls", "Residual risk"],
    "docs/misuse-cases.md": ["Misuse case", "Expected boundary/control"],
    "docs/usability-scenarios-results.md": ["Usability scenarios", "Not Run"],
    "docs/requirements-traceability.md": ["Requirement", "Test", "Artifact"],
    "docs/contribution-testing-release-checklist.md": ["Contribution", "release"],
    "docs/incident-demo-defect-log.md": ["Incident/demo", "Status"],
}


def validate_ticket16_evidence(root: Path) -> list[str]:
    """type-10032026-ticket16: Validate committed synthetic evidence without PII."""
    manifest = json.loads((root / "docs/evidence-manifest-ticket16.json").read_text())
    errors: list[str] = []
    statement = manifest.get("statement", "").lower()
    for forbidden in ("formal wcag", "iso certification", "fda certification", "hipaa certification", "clinical validation"):
        if forbidden in statement and not ("no formal" in statement or "non-certification" in statement):
            errors.append(f"forbidden claim: {forbidden}")
    for key in ("spec", "cases", "artifacts", "automated_tests", "required_sections"):
        if not manifest.get(key):
            errors.append(f"missing manifest field: {key}")
    for relative, sections in REQUIRED.items():
        path = root / relative
        if not path.is_file():
            errors.append(f"missing artifact: {relative}")
            continue
        text = path.read_text().lower()
        for section in sections:
            if section.lower() not in text:
                errors.append(f"missing section {section!r}: {relative}")
    rows = list(csv.reader((root / manifest["cases"]).open(newline="")))
    if len(rows[0]) != 18:
        errors.append(f"canonical header has {len(rows[0])} columns, expected 18")
    ticket_rows = [row for row in rows[1:] if row and row[0].startswith("TC-EXP-01") and int(row[0].split("-")[-1]) >= 132]
    ids = [int(row[0].split("-")[-1]) for row in ticket_rows]
    if ids != list(range(132, 132 + len(ids))) or len(ids) < 8:
        errors.append(f"Ticket16 IDs are not continuous from 0132: {ids}")
    for row in ticket_rows:
        if len(row) != 18 or not row[15] or not row[17]:
            errors.append(f"incomplete canonical row: {row[0] if row else 'blank'}")
    for relative in manifest["artifacts"] + [manifest["spec"], manifest["cases"]]:
        if not (root / relative.split("::")[0]).exists():
            errors.append(f"broken manifest link: {relative}")
    return errors


def test_TC_EXP_0139_ticket16_manifest_validator_is_deterministic():
    """type-10032026-ticket16: The committed evidence manifest validates without PII."""
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root / "docs/evidence-manifest-ticket16.json").read_text())
    assert validate_ticket16_evidence(root) == []
    assert manifest["ticket"] == "Ticket16"
