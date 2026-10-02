"""type-10022026-Maurice: Ticket 07 acceptance coverage, RED before implementation."""
import time
import pytest
from django.test import Client
pytestmark = pytest.mark.django_db

def _client(user):
    client = Client(); client.force_login(user); return client

def _user(role="clinician"):
    from backend.users.models import User
    return User.objects.create_user(username=f"ticket07-{role}-{time.time_ns()}", password="safe", role=role)

def test_TC_EHR_0013_fhir_six_resource_read_and_search():
    client = _client(_user())
    for resource in ("Patient", "MedicationRequest", "AllergyIntolerance", "Condition", "Observation", "Device"):
        response = client.get(f"/fhir/R4/{resource}")
        assert response.status_code == 200
        assert response["Content-Type"] == "application/fhir+json"
        assert response.json()["resourceType"] == "Bundle"

def test_TC_EHR_0014_fhir_failures_are_operation_outcomes(monkeypatch):
    authenticated = _client(_user())
    responses = [
        Client().get("/fhir/R4/Unknown"),
        authenticated.get("/fhir/R4/Unknown"),
        authenticated.get("/fhir/R4/Patient?unsupported=value"),
        authenticated.post("/fhir/R4/Patient"),
    ]

    def fail_seed(_user):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr("backend.users.fhir._ensure_demo_records", fail_seed)
    responses.append(authenticated.get("/fhir/R4/Patient"))

    for response in responses:
        assert response["Content-Type"] == "application/fhir+json"
        assert response.json()["resourceType"] == "OperationOutcome"

def test_TC_EHR_0025_fhir_content_type_and_metadata():
    response = _client(_user()).get("/fhir/R4/Patient")
    assert response["Content-Type"] == "application/fhir+json"
    assert response.json()["type"] == "searchset"

def test_TC_EHR_0029_fhir_read_typical_latency():
    started = time.monotonic(); response = _client(_user()).get("/fhir/R4/Patient/P001")
    assert response.status_code == 200
    assert time.monotonic() - started < 0.5

def test_TC_EHR_0030_fhir_empty_search_is_safe():
    response = _client(_user()).get("/fhir/R4/Patient?name=does-not-exist")
    assert response.status_code == 200
    assert response.json()["total"] == 0

def test_TC_EHR_0037_device_is_seeded_read_only():
    response = _client(_user()).get("/fhir/R4/Device?patient=P001")
    assert response.status_code == 200
    assert response.json()["entry"]
