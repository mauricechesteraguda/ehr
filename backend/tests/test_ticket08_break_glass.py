"""Ticket08 verification: emergency access remains read-only and auditable."""
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.test import Client
from django.utils import timezone

from backend.users.audit import verify_chain
from backend.users.break_glass import request_access, revoke_access
from backend.users.models import AuditEvent, ClinicianPatientAssignment, EmergencyAccessRequest, Patient, User

pytestmark = pytest.mark.django_db


def _session_user(role=User.Role.CLINICIAN, username="bg-clinician"):
    user = User.objects.create_user(username=username, password="safe", role=role, totp_enrolled=True)
    client = Client()
    client.force_login(user)
    session = client.session
    session["totp_authenticated"] = True
    session.save()
    return client, user


def _patient(*, restricted=False):
    return Patient.objects.create(public_id="P002", display_name="Demo Patient Two", birth_date="1975-05-05", restricted_access=restricted)


def test_TC_EXP_0051_grant_break_glass_access_is_30_minutes_and_audited():
    client, clinician = _session_user()
    patient = _patient(restricted=True)
    response = client.post(f"/api/patients/{patient.public_id}/break-glass/", {"justification": "Synthetic emergency justification for review"}, content_type="application/json")
    assert response.status_code == 201
    grant = EmergencyAccessRequest.objects.get(pk=response.json()["id"])
    assert grant.expires_at == grant.requested_at + timedelta(minutes=30)
    assert AuditEvent.objects.filter(resource_type="EmergencyAccessRequest", resource_id=str(grant.pk), action__in=["request", "grant"]).count() == 2
    assert response.json()["patient"] == patient.public_id


def test_TC_EXP_0052_justification_validation_creates_no_grant():
    client, _ = _session_user()
    patient = _patient(restricted=True)
    before = EmergencyAccessRequest.objects.count()
    for reason in ("", "too short", "x" * 501):
        response = client.post(f"/api/patients/{patient.public_id}/break-glass/", {"justification": reason}, content_type="application/json")
        assert response.status_code == 400
    assert EmergencyAccessRequest.objects.count() == before


def test_TC_EXP_0053_role_and_policy_boundaries_are_uniform():
    patient = _patient(restricted=True)
    for role, username in ((User.Role.PATIENT, "bg-patient"), (User.Role.DEVELOPER, "bg-developer")):
        client, _ = _session_user(role, username)
        assert client.post(f"/api/patients/{patient.public_id}/break-glass/", {"justification": "Synthetic emergency justification for review"}, content_type="application/json").status_code == 403
    client, clinician = _session_user(username="bg-unassigned")
    assert client.get(f"/api/patients/{patient.public_id}/").status_code == 403
    grant = request_access(clinician=clinician, patient=patient, justification="Synthetic emergency justification for review")
    assert client.get(f"/api/patients/{patient.public_id}/").status_code == 200
    assert not ClinicianPatientAssignment.objects.filter(clinician=clinician, patient=patient).exists()
    assert grant.state == EmergencyAccessRequest.State.ACTIVE


def test_TC_EXP_0054_expiry_revoke_and_read_only_boundaries_fail_closed():
    client, clinician = _session_user(username="bg-boundary")
    patient = _patient(restricted=True)
    grant = request_access(clinician=clinician, patient=patient, justification="Synthetic emergency justification for review")
    assert client.patch(f"/api/patients/{patient.public_id}/", {"display_name": "No mutation"}, content_type="application/json").status_code == 403
    assert client.post(f"/api/patients/{patient.public_id}/exports/", {"format": "json"}, content_type="application/json").status_code == 403
    assert client.get("/api/patients/").status_code == 200
    assert client.delete(f"/api/patients/{patient.public_id}/break-glass/").status_code == 200
    grant.refresh_from_db()
    assert grant.state == EmergencyAccessRequest.State.REVOKED
    assert client.get(f"/api/patients/{patient.public_id}/").status_code == 403
    grant.state = EmergencyAccessRequest.State.ACTIVE
    grant.expires_at = timezone.now() - timedelta(seconds=1)
    grant.save(update_fields=["state", "expires_at"])
    assert client.get(f"/api/patients/{patient.public_id}/").status_code == 403


def test_TC_EXP_0055_each_emergency_read_audits_and_audit_outage_fails_closed():
    client, clinician = _session_user(username="bg-audit")
    patient = _patient(restricted=True)
    grant = request_access(clinician=clinician, patient=patient, justification="Synthetic emergency justification for review")
    assert client.get(f"/api/patients/{patient.public_id}/").status_code == 200
    assert AuditEvent.objects.filter(actor=clinician, action="read", resource_type="Patient", resource_id=patient.public_id).exists()
    with patch("backend.users.audit.append_audit_event", side_effect=RuntimeError("audit unavailable")):
        assert client.get(f"/api/patients/{patient.public_id}/").status_code == 503
    assert verify_chain()["valid"]
    revoke_access(grant_id=grant.pk, actor=clinician)
    admin_client, _ = _session_user(User.Role.ADMIN, "bg-admin")
    review = admin_client.get("/api/admin/break-glass/")
    assert review.status_code == 200 and any(item["id"] == grant.pk for item in review.json())
    reviewed = admin_client.patch(f"/api/admin/break-glass/{grant.pk}/", {"outcome": "accepted"}, content_type="application/json")
    assert reviewed.status_code == 200 and reviewed.json()["review_outcome"] == "accepted"
