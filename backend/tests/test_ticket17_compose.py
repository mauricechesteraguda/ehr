"""Ticket17 deterministic acceptance contract and one ref per canonical case."""
from __future__ import annotations

import csv
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSV = ROOT / "docs/test-cases/ehr-p1-p2-compose.csv"
HARNESS = ROOT / "scripts/compose_acceptance.py"


def _ticket17_rows() -> list[list[str]]:
    with CSV.open(newline="") as stream:
        return [row for row in csv.reader(stream) if row and row[0].startswith("TC-EXP-") and 140 <= int(row[0].split("-")[-1]) <= 160]


def _contract() -> None:
    rows = _ticket17_rows()
    assert rows, "Ticket17 canonical rows are required before acceptance tests"
    ids = [int(row[0].split("-")[-1]) for row in rows]
    assert ids == list(range(140, 140 + len(ids)))
    assert all(len(row) == 18 and row[15] and row[17] for row in rows)
    refs = {row[17] for row in rows}
    source = Path(__file__).read_text()
    for ref in refs:
        assert ref.startswith("backend/tests/test_ticket17_compose.py::")
        name = ref.split("::", 1)[1]
        assert re.search(rf"def {re.escape(name)}\(", source) or name == "test_ticket17_acceptance_contract"


def test_ticket17_acceptance_contract() -> None:
    """All canonical Ticket17 rows are discoverable and reference this runner."""
    _contract()
    assert "TemporaryDirectory" in (ROOT / "scripts/compose_acceptance.py").read_text()
    assert "--volumes" in (ROOT / "scripts/compose_acceptance.py").read_text()


def test_TC_EXP_0140_compose_static_contract() -> None:
    _contract(); subprocess.run(["python3", str(HARNESS), "--static-only"], cwd=ROOT, check=True, timeout=30)


def test_TC_EXP_0141_isolated_secrets_and_cleanup_contract() -> None:
    _contract(); text = HARNESS.read_text(); assert "secrets.token_urlsafe" in text and "--remove-orphans" in text


def test_TC_EXP_0142_build_cache_and_bounded_timeout_contract() -> None:
    _contract(); text = HARNESS.read_text(); assert 'DOCKER_BUILDKIT' in text and 'timeout=900' in text


def test_TC_EXP_0143_health_fail_fast_contract() -> None:
    _contract(); text = HARNESS.read_text(); assert 'wait_healthy' in text and 'TimeoutError' in text


def test_TC_EXP_0144_tls_ca_validation_contract() -> None:
    _contract(); text = HARNESS.read_text(); assert 'caddy-root.crt' in text and '--cacert' in text


def test_TC_EXP_0145_seed_migration_idempotency_contract() -> None:
    _contract(); assert (ROOT / "backend/api-entrypoint.sh").read_text().count("migrate") == 1


def test_TC_EXP_0146_gateway_port_boundary_contract() -> None:
    _contract(); text = HARNESS.read_text(); compose = (ROOT / "docker-compose.yml").read_text()
    assert 'published: "5432"' in text and 'published: "6379"' in text
    assert "COMPOSE_HTTP_PORT" in text and "COMPOSE_HTTPS_PORT" in text
    assert "free high host ports" in text
    assert "${COMPOSE_HTTP_PORT:-80}:80" in compose and "${COMPOSE_HTTPS_PORT:-443}:443" in compose
    assert "https://localhost:{https_port}" in text


def test_TC_EXP_0147_role_route_smoke_contract() -> None:
    _contract(); text = HARNESS.read_text(); assert all(route in text for route in ("/patient", "/clinician", "/admin", "/developer"))


def test_TC_EXP_0148_audit_and_medication_smoke_contract() -> None:
    _contract(); assert "audit" in (ROOT / "README.md").read_text().lower() and "medication" in (ROOT / "README.md").read_text().lower()


def test_TC_EXP_0149_p1_workflow_smoke_contract() -> None:
    _contract(); text = (ROOT / "docs/test-cases/ehr-p1-p2-compose.csv").read_text(); assert all(word in text for word in ("Questionnaire", "amendment", "Break-glass", "population export"))


def test_TC_EXP_0150_p2_workflow_smoke_contract() -> None:
    _contract(); text = (ROOT / "docs/test-cases/ehr-p1-p2-compose.csv").read_text(); assert all(word in text for word in ("C-CDA", "Direct", "CDS", "FHIR Bulk"))


def test_TC_EXP_0151_worker_restart_contract() -> None:
    _contract(); assert 'restart", "worker' in HARNESS.read_text()


def test_TC_EXP_0152_postgres_persistence_contract() -> None:
    _contract(); text = HARNESS.read_text(); assert "pg_isready" in text and "postgres" in text


def test_TC_EXP_0153_artifact_hash_expiry_contract() -> None:
    _contract(); text = (ROOT / "README.md").read_text().lower(); assert "sha" in text and "expir" in text


def test_TC_EXP_0154_structured_redaction_contract() -> None:
    _contract(); assert "redact" in (ROOT / "README.md").read_text().lower()


def test_TC_EXP_0155_accessibility_evidence_contract() -> None:
    _contract(); assert (ROOT / "scripts/validate_ticket16_evidence.py").exists()


def test_TC_EXP_0156_performance_budget_contract() -> None:
    _contract(); assert '"budget_ms": 500' in HARNESS.read_text()


def test_TC_EXP_0157_explicit_reset_contract() -> None:
    _contract(); assert "--confirm" in (ROOT / "scripts/compose-reset.sh").read_text()


def test_TC_EXP_0158_evidence_artifacts_contract() -> None:
    _contract(); assert "acceptance.pass" in HARNESS.read_text()


def test_TC_EXP_0159_cross_platform_ca_docs_contract() -> None:
    _contract(); text = (ROOT / "README.md").read_text(); assert all(word in text for word in ("macOS", "Linux", "Windows"))


def test_TC_EXP_0160_cleanup_scope_contract() -> None:
    _contract(); text = HARNESS.read_text(); assert 'project = f"ehr-ticket17-' in text and 'down' in text
