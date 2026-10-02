"""Ticket09 acceptance tests: administration, security boundaries, and performance."""
import json
import logging
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.test import Client, override_settings

pytestmark = pytest.mark.django_db


def _user(username, role="admin", active=True):
    from backend.users.models import User

    return User.objects.create_user(
        username=username,
        password="ticket09-password",
        role=role,
        is_active=active,
        totp_enrolled=True,
    )


def _client(user):
    client = Client()
    client.force_login(user)
    session = client.session
    session["totp_authenticated"] = True
    session.save()
    return client


def test_TC_EHR_0082_admin_user_role_management():
    """An administrator can list/change approved roles; a clinician cannot escalate."""
    from backend.users.models import User

    admin = _user("ticket09-admin-82")
    clinician = _user("ticket09-clinician-82", User.Role.CLINICIAN)
    admin_client = _client(admin)
    response = admin_client.get("/api/admin/users/?page_size=100")
    assert response.status_code == 200
    assert any(row["username"] == clinician.username for row in response.json()["results"])
    changed = admin_client.patch(
        f"/api/admin/users/{clinician.pk}/",
        {"role": User.Role.PATIENT},
        content_type="application/json",
    )
    assert changed.status_code == 200
    assert changed.json()["role"] == User.Role.PATIENT
    assert _client(clinician).patch(
        f"/api/admin/users/{admin.pk}/",
        {"role": User.Role.PATIENT},
        content_type="application/json",
    ).status_code == 403


def test_TC_EHR_0083_admin_safeguards():
    """Self-lockout and last-active-admin removal are rejected, peer changes are safe."""
    from backend.users.models import User

    admin = _user("ticket09-admin-83")
    peer = _user("ticket09-peer-83")
    client = _client(admin)
    own = client.patch(f"/api/admin/users/{admin.pk}/", {"is_active": False}, content_type="application/json")
    assert own.status_code == 409
    own_role = client.patch(f"/api/admin/users/{admin.pk}/", {"role": User.Role.CLINICIAN}, content_type="application/json")
    assert own_role.status_code == 409
    assert client.patch(f"/api/admin/users/{peer.pk}/", {"is_active": False}, content_type="application/json").status_code == 200
    peer.delete()
    assert client.patch(f"/api/admin/users/{admin.pk}/", {"is_active": False}, content_type="application/json").status_code == 409


def test_TC_EHR_0084_rule_floor_controls():
    """Rule CRUD validates floors and preserves CRITICAL as an unsuppressible finding."""
    from backend.users.models import InteractionRule

    client = _client(_user("ticket09-admin-84"))
    assert client.get("/api/admin/interaction-rules/").status_code == 200
    for floor in ("LOW", "MODERATE", "HIGH"):
        assert client.post("/api/admin/interaction-rules/", {"severity_floor": floor}, content_type="application/json").status_code == 200
    assert client.post("/api/admin/interaction-rules/", {"severity_floor": "CRITICAL"}, content_type="application/json").status_code == 400
    created = client.post("/api/admin/interaction-rules/", {"kind": "DRUG_DRUG", "medication_code": "A", "related_medication_code": "B", "severity": "CRITICAL", "description": "critical"}, content_type="application/json")
    assert created.status_code == 201
    rule = InteractionRule.objects.get(pk=created.json()["id"])
    assert rule.severity == InteractionRule.Severity.CRITICAL
    assert client.patch(f"/api/admin/interaction-rules/{rule.pk}/", {"active": False}, content_type="application/json").status_code == 200
    assert client.get("/api/admin/interaction-rules/").json()["severity_choices"] == ["LOW", "MODERATE", "HIGH"]


def test_TC_EHR_0085_audit_viewer_separation(caplog):
    """Audit evidence is admin-only, hash-verifiable, and logs contain no secrets or payloads."""
    admin = _user("ticket09-admin-85")
    patient = _user("ticket09-patient-85", "patient")
    admin_client = _client(admin)
    _client(patient).get("/api/auth/session/")
    response = admin_client.get("/api/audit/?page_size=100")
    assert response.status_code == 200
    assert admin_client.get("/api/audit/verify/").json()["valid"] is True
    assert _client(patient).get("/api/audit/").status_code == 403
    with caplog.at_level(logging.INFO):
        admin_client.get("/api/admin/users/")
    rendered = " ".join(record.getMessage() for record in caplog.records)
    assert "ticket09-password" not in rendered
    assert "totp_secret" not in rendered


def test_TC_EHR_0086_inactivity_all_paths():
    """Configured idle expiry applies to session and authorization paths."""
    with override_settings(SESSION_INACTIVITY_SECONDS=10):
        user = _user("ticket09-admin-86")
        client = _client(user)
        session = client.session
        session["last_activity"] = time.time() - 11
        session.save()
        assert client.get("/api/auth/session/").status_code in (401, 403)
        session = client.session
        session["last_activity"] = time.time() - 11
        session["totp_authenticated"] = True
        session.save()
        assert client.get("/oauth/authorize/", {"client_id": "missing"}).status_code in (400, 401, 403)


def test_TC_EHR_0087_headers_and_bounds():
    """Secure responses include hardening headers and reject oversized page/body requests."""
    client = _client(_user("ticket09-admin-87"))
    assert client.cookies["sessionid"]["secure"] is True
    response = client.get("/api/auth/session/", secure=True)
    assert response.status_code == 200
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["X-Frame-Options"] == "DENY"
    assert response["Referrer-Policy"] == "same-origin"
    assert "max-age=" in response["Strict-Transport-Security"]
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(_user("ticket09-csrf-87"))
    assert csrf_client.post("/api/admin/users/", {"username": "csrf", "password": "safe"}).status_code == 403
    assert client.get("/api/admin/users/?page_size=101").status_code == 400
    assert client.get("/fhir/R4/Patient?_count=51").status_code == 400
    oversized = client.post("/api/admin/users/", "x" * (1024 * 1024 + 1), content_type="application/json")
    assert oversized.status_code in (400, 403, 413)


def test_TC_EHR_0088_rate_limits(caplog):
    """Login, MFA, OAuth token, and export bursts return bounded 429s without secrets in logs."""
    cache.clear()
    user = _user("ticket09-admin-88")
    client = Client(REMOTE_ADDR="198.51.100.88")
    with caplog.at_level(logging.INFO):
        login_responses = [client.post("/api/auth/login/", {"username": user.username, "password": "wrong", "otp": "000000"}) for _ in range(9)]
    assert login_responses[-1].status_code == 429
    cache.clear()
    auth_client = _client(user)
    responses = [auth_client.post("/api/auth/enroll/", {}) for _ in range(11)]
    assert responses[-1].status_code == 429
    cache.clear()
    oauth_responses = [client.post("/oauth/token/", {"client_id": "unknown", "client_secret": "secret-token"}) for _ in range(21)]
    assert oauth_responses[-1].status_code == 429
    cache.clear()
    auth_client.get("/api/patients/")
    export_responses = [auth_client.post("/api/patients/P001/exports/", {"format": "invalid"}) for _ in range(11)]
    assert export_responses[-1].status_code == 429
    rendered = " ".join(record.getMessage() for record in caplog.records)
    assert "ticket09-password" not in rendered and "000000" not in rendered


def test_TC_EHR_0089_validation_injection():
    """Malformed roles, pagination, JSON, and injection-shaped identifiers fail safely."""
    from backend.users.models import User

    client = _client(_user("ticket09-admin-89"))
    assert client.post("/api/admin/users/", {"username": "bad", "password": "x", "role": "' OR 1=1 --"}, content_type="application/json").status_code == 400
    assert client.get("/api/admin/users/?page=not-a-number").status_code == 400
    assert client.get("/fhir/R4/Patient/1%27%20OR%201%3D1").status_code in (404, 400)
    malformed = client.post("/api/admin/interaction-rules/", "{", content_type="application/json")
    assert malformed.status_code in (400, 403)
    assert not User.objects.filter(role="' OR 1=1 --").exists()


def test_TC_EHR_0090_demo_terminology():
    """The public terminology artifact is bounded, machine-readable synthetic data with a disclaimer."""
    artifact = json.loads(Path("docs/demo-terminology.json").read_text())
    assert artifact["synthetic_demo"] is True
    assert "synthetic" in artifact["disclaimer"].lower()
    assert set(artifact["subsets"]) == {"race", "ethnicity", "preferred_language", "sex", "sexual_orientation", "gender_identity"}
    assert all(1 <= len(values) <= 10 for values in artifact["subsets"].values())


def test_TC_EHR_0091_measured_performance():
    """Seeded demo page plus every FHIR read/search remains below the 500ms budget."""
    from backend.users.models import User

    from datetime import date
    from backend.users.models import MedicationOrder, MedicationOrderVersion, Patient

    clinician = _user("ticket09-clinician-91", User.Role.CLINICIAN)
    client = _client(clinician)
    client.get("/api/patients/")
    patient = Patient.objects.get(public_id="P001")
    order = MedicationOrder.objects.create(patient=patient, prescriber=clinician)
    version = MedicationOrderVersion.objects.create(order=order, version=1, created_by=clinician, medication_code="demo-med", medication_name="Demo medication", dose=1, dose_unit="tablet", route="oral", frequency="daily", start_date=date(2026, 1, 1), quantity=30, refills=1, indication="demo")
    order.active_version = version
    order.save(update_fields=["active_version"])
    resources = ("Patient", "MedicationRequest", "AllergyIntolerance", "Condition", "Observation", "Device")
    timings = {}
    for resource in resources:
        search_samples, read_samples = [], []
        for _ in range(3):
            started = time.perf_counter()
            response = client.get(f"/fhir/R4/{resource}?_count=20")
            search_samples.append((time.perf_counter() - started) * 1000)
            assert response.status_code == 200
            resource_id = response.json()["entry"][0]["resource"]["id"]
            started = time.perf_counter()
            assert client.get(f"/fhir/R4/{resource}/{resource_id}").status_code == 200
            read_samples.append((time.perf_counter() - started) * 1000)
        search_samples.sort(); read_samples.sort()
        timings[f"{resource}.search"] = {"max_ms": round(max(search_samples), 2), "p95_ms": round(search_samples[min(2, int(len(search_samples) * .95))], 2)}
        timings[f"{resource}.read"] = {"max_ms": round(max(read_samples), 2), "p95_ms": round(read_samples[min(2, int(len(read_samples) * .95))], 2)}
    assert max(value["max_ms"] for value in timings.values()) < 500
    print(f"Ticket09 performance timings: {json.dumps(timings, sort_keys=True)}")
