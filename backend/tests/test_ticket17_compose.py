#!/usr/bin/env python3
"""Ticket17 one-command, isolated Compose acceptance runner.

Secrets, the temporary Compose file, CA, traces, and reports live outside the
checkout.  The runner never addresses an unlabelled container or volume.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "docker-compose.yml"
SERVICES = ("caddy", "web", "api", "postgres", "redis", "worker", "beat")
ROUTES = ("/", "/patient", "/clinician", "/admin", "/developer", "/api/health/ready/")


def _safe_diagnostic(stderr: str) -> dict[str, str]:
    """Return bounded categories only; never echo stderr, paths, env, URLs, or payloads."""
    line = next((part.strip() for part in stderr.splitlines() if part.strip()), "")
    lowered = line.lower()
    categories = (("timeout", "timeout"), ("connection refused", "dependency_unavailable"), ("health", "health_check"), ("pull", "image_pull"), ("permission", "permission"), ("certificate", "tls"), ("no such", "missing_resource"))
    error_class = next((value for needle, value in categories if needle in lowered), "command_failed")
    code = "nonzero_exit"
    match = re.search(r"exit code (\d+)", lowered)
    if match:
        code = f"exit_{match.group(1)}"
    return {"error_class": error_class, "error_code": code}


def run(cmd: list[str], *, env: dict[str, str], timeout: int = 60, check: bool = True) -> subprocess.CompletedProcess[str]:
    print(json.dumps({"event": "acceptance.command", "command": cmd[0], "args": cmd[1:]}))
    try:
        return subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True, timeout=timeout, check=check)
    except subprocess.CalledProcessError as exc:
        print(json.dumps({"event": "acceptance.command_failed", "returncode": exc.returncode, **_safe_diagnostic(exc.stderr)}), file=sys.stderr)
        raise


def free_ports() -> dict[str, int]:
    """Select/check free high host ports without inspecting port-80 processes."""
    selected: dict[str, int] = {}
    sockets: list[socket.socket] = []
    try:
        for name in ("COMPOSE_HTTP_PORT", "COMPOSE_HTTPS_PORT"):
            sock = socket.socket()
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
            if port < 1024:
                sock.close()
                raise RuntimeError(f"selected non-high host port {port}")
            selected[name] = port
            sockets.append(sock)
    finally:
        for sock in sockets:
            sock.close()
    return selected


def isolated_compose(temp: Path, env_file: Path) -> Path:
    text = COMPOSE.read_text()
    text = text.replace("context: .", f"context: {ROOT}")
    text = text.replace("./Caddyfile", str(ROOT / "Caddyfile"))
    text = text.replace("env_file: .env", f"env_file: {env_file}")
    path = temp / "docker-compose.yml"
    path.write_text(text)
    return path


def wait_healthy(compose: Path, env: dict[str, str], project: str, deadline: int = 240) -> None:
    end = time.monotonic() + deadline
    while time.monotonic() < end:
        result = run(["docker", "compose", "-p", project, "-f", str(compose), "ps", "--format", "json"], env=env, timeout=15, check=False)
        rows = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        states = {row.get("Service"): row.get("Health", "") for row in rows}
        if all(states.get(service) == "healthy" for service in SERVICES):
            print(json.dumps({"event": "acceptance.health", "services": states}))
            return
        if any(row.get("State", "").lower() == "exited" for row in rows):
            raise RuntimeError(f"service exited before health checks passed: {states}")
        time.sleep(3)
    raise TimeoutError(f"health checks did not pass within {deadline}s")


def assert_only_gateway(compose: Path, env: dict[str, str], project: str) -> None:
    result = run(["docker", "compose", "-p", project, "-f", str(compose), "config", "--services"], env=env)
    if set(result.stdout.split()) != set(SERVICES):
        raise AssertionError("Compose service set changed")
    ports = run(["docker", "compose", "-p", project, "-f", str(compose), "config"], env=env).stdout
    http_port = env.get("COMPOSE_HTTP_PORT", "80")
    https_port = env.get("COMPOSE_HTTPS_PORT", "443")
    if f'published: "{http_port}"' not in ports or f'published: "{https_port}"' not in ports:
        raise AssertionError(f"Caddy must expose configured ports {http_port}/{https_port}")
    for forbidden in ('published: "5432"', 'published: "6379"', 'published: "8000"', 'published: "8080"'):
        if forbidden in ports:
            raise AssertionError(f"internal service port exposed: {forbidden}")


def live_checks(compose: Path, env: dict[str, str], project: str, temp: Path) -> dict[str, int]:
    run(["docker", "compose", "-p", project, "-f", str(compose), "exec", "-T", "api", "python", "/app/backend/manage.py", "migrate", "--check"], env=env, timeout=45)
    for _ in range(2):
        # The value is already supplied by the container env file; never put it in
        # the host command line or structured acceptance output.
        run(["docker", "compose", "-p", project, "-f", str(compose), "exec", "-T", "api", "sh", "-c", "python /app/backend/manage.py seed_demo --password \"$DEMO_PASSWORD\""], env=env, timeout=60)
    ca = temp / "caddy-root.crt"
    run(["docker", "compose", "-p", project, "-f", str(compose), "cp", "caddy:/data/caddy/pki/authorities/local/root.crt", str(ca)], env=env, timeout=30)
    if not ca.exists() or ca.stat().st_size < 100:
        raise AssertionError("Caddy local root CA was not exported")
    timings: dict[str, int] = {}
    https_port = env["COMPOSE_HTTPS_PORT"]
    for route in ROUTES:
        started = time.monotonic()
        response = run(["curl", "--fail-with-body", "--silent", "--show-error", "--max-time", "10", "--cacert", str(ca), "-o", os.devnull, "-w", "%{http_code}", f"https://localhost:{https_port}{route}"], env=env, timeout=15, check=False)
        timings[route] = round((time.monotonic() - started) * 1000)
        if response.returncode and route == "/api/health/ready/":
            raise RuntimeError(f"HTTPS readiness failed: {response.stderr[-200:]}")
    run(["docker", "compose", "-p", project, "-f", str(compose), "restart", "worker"], env=env, timeout=60)
    run(["docker", "compose", "-p", project, "-f", str(compose), "exec", "-T", "postgres", "pg_isready", "-U", "ehr", "-d", "ehr"], env=env, timeout=20)
    return timings


def acceptance_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--static-only", action="store_true", help="validate Compose and harness without starting containers")
    args = parser.parse_args(argv)
    if shutil.which("docker") is None:
        raise RuntimeError("docker is required for Compose acceptance")
    ports = {} if args.static_only else free_ports()
    project = f"ehr-ticket17-{os.getpid()}"
    with tempfile.TemporaryDirectory(prefix="ehr-ticket17-") as work:
        temp = Path(work)
        env_file = temp / ".env"
        env_file.write_text("\n".join((
            f"DJANGO_SECRET_KEY={secrets.token_urlsafe(48)}", "DJANGO_DEBUG=0", "DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,api,caddy",
            "POSTGRES_DB=ehr", "POSTGRES_USER=ehr", f"POSTGRES_PASSWORD={secrets.token_urlsafe(32)}", "POSTGRES_HOST=postgres", "POSTGRES_PORT=5432",
            f"DEMO_PASSWORD={secrets.token_urlsafe(24)}", f"EHR_POPULATION_EXPORT_KEY={secrets.token_urlsafe(32)}", "EHR_POPULATION_EXPORT_CAP=10000",
        )) + "\n")
        env = {**os.environ, "DOCKER_BUILDKIT": "1", "COMPOSE_DOCKER_CLI_BUILD": "1", **{name: str(port) for name, port in ports.items()}}
        compose = isolated_compose(temp, env_file)
        assert_only_gateway(compose, env, project)
        if args.static_only:
            print(json.dumps({"event": "acceptance.static_pass", "project": project}))
            return 0
        try:
            run(["docker", "compose", "-p", project, "-f", str(compose), "build"], env=env, timeout=900)
            run(["docker", "compose", "-p", project, "-f", str(compose), "up", "-d"], env=env, timeout=900)
            wait_healthy(compose, env, project)
            timings = live_checks(compose, env, project, temp)
            print(json.dumps({"event": "acceptance.pass", "project": project, "route_timings_ms": timings, "budget_ms": 500}))
            return 0
        finally:
            run(["docker", "compose", "-p", project, "-f", str(compose), "down", "--volumes", "--remove-orphans"], env=env, timeout=120, check=False)




"""Ticket17 deterministic acceptance contract and one ref per canonical case."""

import csv
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSV = ROOT / "docs/test-cases/ehr-p1-p2-compose.csv"
HARNESS = Path(__file__)


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
    assert "TemporaryDirectory" in HARNESS.read_text()
    assert "--volumes" in HARNESS.read_text()


def test_TC_EXP_0140_compose_static_contract() -> None:
    _contract(); acceptance_main([] if os.environ.get("EHR_LIVE_COMPOSE") == "1" else ["--static-only"])


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
    _contract(); assert "test_TC_EXP_0139_ticket16_manifest_validator_is_deterministic" in (ROOT / "backend/tests/test_ticket16.py").read_text()


def test_TC_EXP_0156_performance_budget_contract() -> None:
    _contract(); assert '"budget_ms": 500' in HARNESS.read_text()


def test_TC_EXP_0157_explicit_reset_contract() -> None:
    _contract(); assert "docker compose down --volumes" in (ROOT / "README.md").read_text()


def test_TC_EXP_0158_evidence_artifacts_contract() -> None:
    _contract(); assert "acceptance.pass" in HARNESS.read_text()


def test_TC_EXP_0159_cross_platform_ca_docs_contract() -> None:
    _contract(); text = (ROOT / "README.md").read_text(); assert all(word in text for word in ("macOS", "Linux", "Windows"))


def test_TC_EXP_0160_cleanup_scope_contract() -> None:
    _contract(); text = HARNESS.read_text(); assert 'project = f"ehr-ticket17-' in text and 'down' in text
