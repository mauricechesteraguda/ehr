"""Ticket 06: authorized, exact-byte, expiring synthetic patient downloads."""
from datetime import date, timedelta
import hashlib
import json

import pytest
from django.utils import timezone


def _user(role, name):
    from django.contrib.auth import get_user_model
    return get_user_model().objects.create_user(username=name, password="safe", role=role)


@pytest.fixture
def patient():
    from backend.users.models import Patient
    return Patient.objects.create(public_id="P06", display_name="Synthetic P06", birth_date=date(1980, 1, 1))


@pytest.mark.django_db(transaction=True)
def test_TC_EHR_0064_authorized_json_has_dictionary_and_exact_hash(client, patient):
    clinician = _user("clinician", "clinician-0064")
    client.force_login(clinician)
    response = client.post(f"/api/patients/{patient.public_id}/exports/", {"format": "json"})
    assert response.status_code == 201
    metadata = response.json()
    download = client.get(metadata["download_url"])
    assert download.status_code == 200
    downloaded = b"".join(download.streaming_content)
    assert hashlib.sha256(downloaded).hexdigest() == metadata["sha256"]
    body = json.loads(downloaded)
    assert body["synthetic_demo"] is True and "data_dictionary" in body


@pytest.mark.django_db
def test_TC_EHR_0065_patient_self_only_and_clinician_authorization(client, patient):
    patient_user = _user("patient", "patient-0065")
    patient.owner = patient_user; patient.save(update_fields=["owner"])
    client.force_login(_user("patient", "patient-other-0065"))
    assert client.post(f"/api/patients/{patient.public_id}/exports/", {"format": "json"}).status_code == 403
    client.force_login(patient_user)
    assert client.post(f"/api/patients/{patient.public_id}/exports/", {"format": "pdf"}).status_code == 201


@pytest.mark.django_db
def test_TC_EHR_0066_expiry_denies_and_deletes_artifact(client, patient):
    from backend.users.models import PatientExport
    clinician = _user("clinician", "clinician-0066"); client.force_login(clinician)
    response = client.post(f"/api/patients/{patient.public_id}/exports/", {"format": "json"}).json()
    artifact = PatientExport.objects.get(artifact_id=response["id"])
    artifact.expires_at = timezone.now() - timedelta(seconds=1); artifact.save(update_fields=["expires_at"])
    assert client.get(response["download_url"]).status_code == 410
    assert not PatientExport.objects.filter(pk=artifact.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_TC_EHR_0067_failed_audit_leaves_no_file_or_row(client, patient, monkeypatch):
    from backend.users import audit
    from backend.users.models import PatientExport
    clinician = _user("clinician", "clinician-0067"); client.force_login(clinician)
    monkeypatch.setattr(audit, "append_audit_event", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("audit")))
    assert client.post(f"/api/patients/{patient.public_id}/exports/", {"format": "json"}).status_code == 503
    assert PatientExport.objects.count() == 0


@pytest.mark.django_db
def test_TC_EHR_0068_duplicate_slot_is_reused(client, patient):
    clinician = _user("clinician", "clinician-0068"); client.force_login(clinician)
    first = client.post(f"/api/patients/{patient.public_id}/exports/", {"format": "json"}).json()
    second = client.post(f"/api/patients/{patient.public_id}/exports/", {"format": "json"}).json()
    assert first["id"] == second["id"]


@pytest.mark.django_db
def test_TC_EHR_0069_admin_is_not_an_export_actor(client, patient):
    client.force_login(_user("admin", "admin-0069"))
    assert client.post(f"/api/patients/{patient.public_id}/exports/", {"format": "json"}).status_code == 403


def test_TC_EHR_0071_trace_locations_are_repository_relative(tmp_path, monkeypatch):
    """TC-EHR-0071: trace diagnostics never expose absolute filesystem paths."""
    from backend.users import tracing

    trace_file = tmp_path / "trace.jsonl"
    monkeypatch.setattr(tracing, "TRACE_FILE", trace_file)

    @tracing.trace_function
    def traced_failure():
        raise RuntimeError("diagnostic message must not be recorded")

    with pytest.raises(RuntimeError):
        traced_failure()

    event = json.loads(trace_file.read_text().splitlines()[-1])
    assert event["stack_trace"]
    assert all(not location.startswith(("/", "~")) for location in event["stack_trace"])
    assert all("/Users/" not in location and "/home/" not in location for location in event["stack_trace"])
    assert all("diagnostic message" not in location for location in event["stack_trace"])
