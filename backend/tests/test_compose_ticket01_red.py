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


def test_compose_web_non_root_has_writable_runtime_paths():
    """The nginx worker must not rely on root-owned /var/run defaults."""
    config = _read("web/nginx.conf")
    dockerfile = _read("web/Dockerfile")
    assert "pid /tmp/nginx.pid;" in config
    assert "client_body_temp_path /tmp/nginx/client_temp;" in config
    assert "proxy_temp_path /tmp/nginx/proxy_temp;" in config
    assert "mkdir -p /tmp/nginx" in dockerfile
    assert "chown -R nginx:nginx /tmp/nginx" in dockerfile


def test_readiness_contract_is_explicit_and_fail_safe():
    """Readiness must expose only a stable state while startup is incomplete."""
    source = _read("backend/users/health.py")
    assert 'status="unready"' in source or '"status": "unready"' in source
    assert "status=503" in source
    assert "status=500" not in source
    assert "TRACE_FILE: /run/ehr/api-trace.jsonl" in _read("docker-compose.yml")


def test_compose_celery_services_configure_django_before_imports():
    """Celery imports Django-backed tasks during worker startup."""
    compose = _read("docker-compose.yml")
    assert compose.count("DJANGO_SETTINGS_MODULE: backend.config.settings") >= 2


def test_caddy_routes_use_valid_block_syntax():
    """The gateway must parse and stay up before route acceptance runs."""
    caddy = _read("Caddyfile")
    assert "handle @api {\n        reverse_proxy api:8000\n    }" in caddy
    assert "handle {\n        reverse_proxy web:8080\n    }" in caddy
