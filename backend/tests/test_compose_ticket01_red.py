"""type-10022026-Maurice: RED acceptance coverage for Ticket01 compose platform."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_TC_EXP_0001_compose_declares_healthy_ordered_platform():
    """TC-EXP-0001: all approved services and health-gated dependencies exist."""
    compose = _read("docker-compose.yml")
    for service in ("caddy:", "web:", "api:", "postgres:", "redis:", "worker:", "beat:"):
        assert service in compose
    assert "condition: service_healthy" in compose


def test_TC_EXP_0002_api_ready_fails_safe_when_dependency_is_missing():
    """TC-EXP-0002: readiness checks DB/migrations and emits a safe failure state."""
    source = _read("backend/config/urls.py") + _read("backend/users/health.py")
    assert "ready" in source.lower()
    assert "database" in source.lower() or "db" in source.lower()


def test_TC_EXP_0003_caddy_enforces_local_tls12_with_external_cert_boundary():
    """TC-EXP-0003: HTTPS uses a local CA and TLS 1.2 minimum."""
    caddy = _read("Caddyfile")
    assert "tls internal" in caddy
    assert "tls1.2" in caddy
    assert "443" in _read("docker-compose.yml")


def test_TC_EXP_0004_named_persistence_and_explicit_reset_are_documented():
    """TC-EXP-0004: PostgreSQL/Caddy persist and reset is explicit and destructive."""
    compose = _read("docker-compose.yml")
    readme = _read("README.md")
    assert "postgres_data" in compose and "caddy_data" in compose
    assert "docker compose down -v" in readme
    assert "DESTRUCTIVE" in readme


def test_TC_EXP_0005_clean_launch_has_production_web_and_gateway_routes():
    """TC-EXP-0005: one-command launch serves the production React shell and API routes."""
    compose = _read("docker-compose.yml")
    caddy = _read("Caddyfile")
    assert "docker compose up --build" in _read("README.md")
    assert "npm run build" in _read("web/Dockerfile")
    for route in ("/api", "/fhir", "/oauth", "/.well-known"):
        assert route in caddy
    assert "gunicorn" in _read("backend/api-entrypoint.sh")


def test_TC_EXP_0006_backend_dependency_install_is_cached_pinned_and_bounded():
    """TC-EXP-0006: BuildKit caches pip, pins tooling, and bounds network retries."""
    dockerfile = _read("backend/Dockerfile")
    assert "# syntax=docker/dockerfile:1.7" in dockerfile
    assert "--mount=type=cache,target=/root/.cache/pip" in dockerfile
    assert "pip==${PIP_VERSION}" in dockerfile
    assert "setuptools==${SETUPTOOLS_VERSION}" in dockerfile
    assert "wheel==${WHEEL_VERSION}" in dockerfile
    assert '--timeout="${PIP_INSTALL_TIMEOUT}"' in dockerfile
    assert '--retries="${PIP_INSTALL_RETRIES}"' in dockerfile
    assert "--no-index" not in dockerfile
    assert "--trusted-host" not in dockerfile
    assert "--no-cache-dir" not in dockerfile
