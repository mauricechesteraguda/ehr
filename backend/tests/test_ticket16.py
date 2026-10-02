"""Ticket16 machine evidence acceptance; synthetic metadata only."""

import json
import subprocess
from pathlib import Path


def test_TC_EXP_0139_ticket16_manifest_validator_is_deterministic():
    """type-10032026-ticket16: The committed evidence manifest validates without PII."""
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root / "docs/evidence-manifest-ticket16.json").read_text())
    result = subprocess.run(
        ["python3", "scripts/validate_ticket16_evidence.py"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert manifest["ticket"] == "Ticket16"
    assert "PII" not in result.stdout
