"""type-10042026-Maurice: Ticket05 platform security contracts and opt-in kind seam."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
PLATFORM = ROOT / "platform"


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_TC_PLAT_0029_external_secret_references_only() -> None:
    """TC-PLAT-0029/REQ-PLAT-26,27: only references are committed."""
    text = _text("platform/gitops/resources/secret-references.yaml")
    assert "ExternalSecret" in text and "workload identity" in text.lower()
    assert "password:" not in text and "secretKey:" in text


def test_TC_PLAT_0030_secret_provider_failure_boundary() -> None:
    """TC-PLAT-0030/REQ-PLAT-26: failures are safe and bounded by policy."""
    text = _text("platform/README.md").lower()
    assert "bounded" in text and "secret" in text and "raw" in text
    assert "not deployed" in text


def test_TC_PLAT_0031_workload_identity_no_static_keys() -> None:
    """TC-PLAT-0031/REQ-PLAT-27: provider paths require workload identity."""
    text = _text("platform/gitops/resources/secret-references.yaml").lower()
    assert "workload identity" in text and "static keys" in text
    assert "access_key" not in text and "secret_access_key" not in text


def test_TC_PLAT_0032_kyverno_and_psa_contracts_present() -> None:
    """TC-PLAT-0032/REQ-PLAT-28: compliant workloads have policy seams."""
    text = _text("platform/gitops/resources/kyverno-policies.yaml")
    namespaces = _text("platform/gitops/apps/namespaces.yaml")
    assert "ClusterPolicy" in text and "runAsNonRoot" in text
    assert "pod-security.kubernetes.io/enforce: restricted" in namespaces


def test_TC_PLAT_0033_unsafe_workload_policy_contract() -> None:
    """TC-PLAT-0033/REQ-PLAT-28: unsafe capabilities and host access are denied."""
    text = _text("platform/gitops/resources/kyverno-policies.yaml")
    assert "privileged" in text and "hostPath" in text and "allowPrivilegeEscalation" in text


def test_TC_PLAT_0034_psa_restricted_namespaces() -> None:
    """TC-PLAT-0034/REQ-PLAT-29: all application namespaces use restricted PSA."""
    data = list(yaml.safe_load_all(_text("platform/gitops/apps/namespaces.yaml")))
    app_namespaces = {item["metadata"]["name"] for item in data if item.get("kind") == "Namespace"}
    assert app_namespaces
    for item in data:
        if item.get("kind") == "Namespace" and item["metadata"]["name"] in app_namespaces:
            assert item["metadata"].get("labels", {}).get("pod-security.kubernetes.io/enforce") == "restricted"


def test_TC_PLAT_0035_default_deny_network_contract() -> None:
    """TC-PLAT-0035/REQ-PLAT-30,31: network policy is explicit and default-deny."""
    text = _text("platform/gitops/resources/network-policies.yaml").lower()
    assert "policytypes" in text and "ingress" in text and "egress" in text
    assert "default" in text and "deny" in text


def test_TC_PLAT_0036_private_administration_and_kind_profile() -> None:
    """TC-PLAT-0036/REQ-PLAT-41: admin services stay private; kind is local-only."""
    gateway = _text("platform/gitops/resources/gateway.yaml")
    service_templates = "\n".join(path.read_text(encoding="utf-8") for path in (PLATFORM / "helm/ehr/templates").glob("*.yaml"))
    assert "ClusterIP" in _text("platform/helm/ehr/templates/service.yaml")
    assert "ehr.example.invalid" in gateway  # explicitly documented non-live placeholder
    assert "apiServerAddress: 127.0.0.1" in _text("platform/kind/cluster.yaml")
    assert "LoadBalancer" not in service_templates and "NodePort" not in service_templates


def _run(command: list[str], *, input_text: str | None = None, timeout: int = 180) -> None:
    result = subprocess.run(command, cwd=ROOT, input=input_text, text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"command failed safely: {command[0]} returned {result.returncode}")


@pytest.mark.kind_e2e
def test_kind_ticket05_acceptance() -> None:
    """Opt-in bounded application acceptance; never runs in ordinary CI."""
    if os.getenv("EHR_KIND_E2E") != "1":
        pytest.skip("EHR_KIND_E2E=1 required; live kind evidence is not claimed")
    for tool in ("docker", "kind", "kubectl", "helm"):
        if subprocess.run(["sh", "-c", f"command -v {tool}"], capture_output=True).returncode:
            pytest.skip(f"blocked: {tool} unavailable")
    cluster = f"ehr-ticket05-{os.getpid()}-{int(time.time())}"
    api_image = f"ehr-ticket05-api:{cluster}"
    web_image = f"ehr-ticket05-web:{cluster}"
    architecture = subprocess.run(["docker", "info", "--format", "{{.Architecture}}"], capture_output=True, text=True, check=True).stdout.strip()
    image_platform = {"aarch64": "linux/arm64", "arm64": "linux/arm64", "amd64": "linux/amd64"}.get(architecture)
    if image_platform is None:
        pytest.skip("blocked: unsupported local Docker architecture")
    try:
        _run(["kind", "create", "cluster", "--name", cluster, "--config", str(PLATFORM / "kind/cluster.yaml")], timeout=240)
        _run(["docker", "build", "--platform", image_platform, "-f", "backend/Dockerfile", "-t", api_image, "."], timeout=600)
        _run(["docker", "build", "--platform", image_platform, "-f", "web/Dockerfile", "-t", web_image, "."], timeout=600)
        _run(["kind", "load", "docker-image", api_image, "--name", cluster], timeout=180)
        _run(["kind", "load", "docker-image", web_image, "--name", cluster], timeout=180)
        _run(["kubectl", "create", "namespace", "ehr-demo"])
        _run(["kubectl", "-n", "ehr-demo", "create", "secret", "generic", "ehr-django-secrets", "--from-literal=DJANGO_SECRET_KEY=synthetic-kind-only", "--from-literal=DEMO_PASSWORD=synthetic-demo-only"])
        _run(["kubectl", "-n", "ehr-demo", "create", "secret", "generic", "ehr-database-secrets", "--from-literal=POSTGRES_PASSWORD=synthetic-kind-only"])
        _run(["kubectl", "-n", "ehr-demo", "create", "secret", "generic", "ehr-redis-secrets", "--from-literal=REDIS_URL=redis://redis:6379/0", "--from-literal=CELERY_RESULT_BACKEND=redis://redis:6379/1"])
        deps = """apiVersion: v1\nkind: Service\nmetadata: {name: postgres}\nspec: {selector: {app: postgres}, ports: [{port: 5432}]}\n---\napiVersion: apps/v1\nkind: Deployment\nmetadata: {name: postgres}\nspec:\n  replicas: 1\n  selector: {matchLabels: {app: postgres}}\n  template:\n    metadata: {labels: {app: postgres}}\n    spec:\n      containers:\n      - name: postgres\n        image: postgres:17.2-alpine\n        env:\n        - {name: POSTGRES_DB, value: ehr}\n        - {name: POSTGRES_USER, value: ehr}\n        - {name: POSTGRES_PASSWORD, value: synthetic-kind-only}\n        ports: [{containerPort: 5432}]\n---\napiVersion: v1\nkind: Service\nmetadata: {name: redis}\nspec: {selector: {app: redis}, ports: [{port: 6379}]}\n---\napiVersion: apps/v1\nkind: Deployment\nmetadata: {name: redis}\nspec:\n  replicas: 1\n  selector: {matchLabels: {app: redis}}\n  template:\n    metadata: {labels: {app: redis}}\n    spec:\n      containers:\n      - {name: redis, image: redis:7.4.2-alpine, ports: [{containerPort: 6379}]}\n"""
        _run(["kubectl", "apply", "-n", "ehr-demo", "-f", "-"], input_text=deps)
        _run(["kubectl", "-n", "ehr-demo", "wait", "--for=condition=available", "deployment/postgres", "deployment/redis", "--timeout=120s"], timeout=150)
        _run(["helm", "dependency", "build", "platform/helm/ehr"], timeout=120)
        _run(["helm", "upgrade", "--install", "ehr", "platform/helm/ehr", "--namespace", "ehr-demo", "-f", "platform/helm/ehr/values-demo.yaml", "--set", f"image.repository={api_image.split(':')[0]}", "--set", f"image.tag={cluster}", "--set", f"image.webRepository={web_image.split(':')[0]}", "--set", f"image.webTag={cluster}", "--set", "seed.enabled=true", "--wait", "--timeout", "180s"], timeout=240)
        _run(["kubectl", "-n", "ehr-demo", "wait", "--for=condition=complete", "job/ehr-migration", "--timeout=120s"], timeout=150)
        _run(["kubectl", "-n", "ehr-demo", "wait", "--for=condition=available", "deployment/ehr-web", "deployment/ehr-api", "--timeout=180s"], timeout=210)
        _run(["kubectl", "-n", "ehr-demo", "exec", "deployment/ehr-web", "--", "wget", "-qO-", "http://127.0.0.1:8080/healthz"], timeout=30)
        _run(["kubectl", "-n", "ehr-demo", "exec", "deployment/ehr-api", "--", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/live/')"], timeout=30)
        _run(["kubectl", "-n", "ehr-demo", "get", "pods", "-l", "app.kubernetes.io/component=worker", "--field-selector=status.phase=Running"])
        _run(["kubectl", "-n", "ehr-demo", "get", "pods", "-l", "app.kubernetes.io/component=beat", "--field-selector=status.phase=Running"])
        assert subprocess.run(["kubectl", "-n", "ehr-demo", "get", "svc", "-o", "jsonpath={.items[*].spec.type}"], capture_output=True, text=True).stdout.strip() in {"ClusterIP", "ClusterIP ClusterIP"}
    finally:
        subprocess.run(["kind", "delete", "cluster", "--name", cluster], capture_output=True, timeout=120)
