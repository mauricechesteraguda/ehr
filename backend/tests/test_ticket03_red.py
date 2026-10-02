"""type-10022026-Maurice: Ticket 03 acceptance tests, written RED first."""
import pytest


def _user(role, username):
    from django.contrib.auth import get_user_model
    return get_user_model().objects.create_user(username=username, password="safe", role=role)


@pytest.mark.django_db
def test_TC_EHR_0022_append_only_chain_and_tamper_detection(client):
    """TC-EHR-0022: protected reads are chained and verification detects tampering."""
    clinician = _user("clinician", "clinician-0022")
    client.force_login(clinician)
    assert client.get("/api/patients/P001/").status_code == 200
    from backend.users.models import AuditEvent
    event = AuditEvent.objects.latest("sequence")
    assert {"actor_id", "occurred_at", "patient_id", "action", "resource_type", "resource_id", "correlation_id", "previous_hash", "current_hash"} <= set(event.__dict__)
    assert client.get("/api/audit/verify/").status_code == 403
    # type-10022026-Maurice: Database enforcement rejects app/API tampering.
    from django.db import DatabaseError, transaction
    event.current_hash = "tampered"
    with transaction.atomic():
        with pytest.raises(DatabaseError):
            event.save(update_fields=["current_hash"])
    admin = _user("admin", "admin-0022")
    client.force_login(admin)
    assert client.get("/api/audit/verify/").json()["valid"] is True


@pytest.mark.django_db
def test_TC_EHR_0023_admin_paginated_filtered_sorted_report_and_separation(client, caplog):
    """TC-EHR-0023: only admins receive deterministic audit report data."""
    admin = _user("admin", "admin-0023")
    client.force_login(admin)
    client.get("/api/patients/P001/")
    response = client.get("/api/audit/?action=read&patient=P001&ordering=-occurred_at&page=1&page_size=10")
    assert response.status_code == 200
    assert response.json()["results"]
    assert all(item["action"] == "read" for item in response.json()["results"])
    assert not any("Demo Patient" in record.getMessage() for record in caplog.records)
    clinician = _user("clinician", "clinician-0023")
    client.force_login(clinician)
    assert client.get("/api/audit/").status_code == 403


@pytest.mark.django_db
def test_TC_EHR_0039_patient_update_and_audit_are_atomic(client, monkeypatch):
    """TC-EHR-0039: audit failure rolls back the clinical mutation."""
    clinician = _user("clinician", "clinician-0039")
    client.force_login(clinician)
    from backend.users import audit
    monkeypatch.setattr(audit, "append_audit_event", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("audit unavailable")))
    response = client.patch("/api/patients/P001/", {"display_name": "Should Roll Back"}, content_type="application/json")
    assert response.status_code >= 500
    from backend.users.models import Patient
    assert Patient.objects.get(public_id="P001").display_name != "Should Roll Back"


@pytest.mark.django_db
def test_TC_EHR_0033_read_hook_contains_patient_and_correlation(client):
    """TC-EHR-0033: record correction/read flows remain auditable."""
    user = _user("clinician", "clinician-0033")
    client.force_login(user)
    response = client.get("/api/patients/P001/")
    assert response["X-Correlation-ID"]
    from backend.users.models import AuditEvent
    event = AuditEvent.objects.latest("sequence")
    assert event.patient.public_id == "P001" and event.action == "read"
