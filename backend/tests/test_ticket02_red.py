"""type-10022026-Maurice: Ticket 02 acceptance tests, written RED first."""

import pytest


def _user(role, username):
    from django.contrib.auth import get_user_model
    return get_user_model().objects.create_user(username=username, password="safe", role=role)


@pytest.mark.django_db
def test_TC_EHR_0007_synthetic_demographics_are_coded_and_displayed(client):
    """TC-EHR-0007: the patient detail includes all approved coded demographics."""
    clinician = _user("clinician", "clinician-0007")
    client.force_login(clinician)
    response = client.get("/api/patients/P001/")
    assert response.status_code == 200
    assert {"race", "ethnicity", "preferred_language", "sex", "sexual_orientation", "gender_identity", "birth_date", "death_date"} <= response.json().keys()


@pytest.mark.django_db
def test_TC_EHR_0008_invalid_demographic_codes_and_dates_are_rejected(client):
    """TC-EHR-0008: invalid demographic values cannot be persisted."""
    clinician = _user("clinician", "clinician-0008")
    client.force_login(clinician)
    response = client.patch("/api/patients/P001/", {"race": "NOT-A-CODE", "death_date": "2019-01-01"}, content_type="application/json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_TC_EHR_0017_clinician_search_and_patient_self_only_detail(client):
    """TC-EHR-0017: clinicians see all synthetic patients; patients see only their own."""
    patient = _user("patient", "patient-0017")
    client.force_login(patient)
    own = client.get("/api/patients/P001/")
    other = client.get("/api/patients/P002/")
    assert own.status_code == 200 and other.status_code == 403


@pytest.mark.django_db
def test_TC_EHR_0030_patient_search_has_safe_empty_loading_contract(client):
    """TC-EHR-0030: empty search is a successful empty result, not an unbounded read."""
    clinician = _user("clinician", "clinician-0030")
    client.force_login(clinician)
    response = client.get("/api/patients/?q=does-not-exist")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.django_db
def test_TC_EHR_0037_device_is_read_only(client):
    """TC-EHR-0037: synthetic devices are readable but not writable."""
    clinician = _user("clinician", "clinician-0037")
    client.force_login(clinician)
    response = client.post("/api/patients/P001/devices/", {"status": "changed"}, content_type="application/json")
    assert response.status_code == 405


@pytest.mark.django_db
def test_TC_EHR_0028_patient_payload_declares_synthetic_only(client):
    """TC-EHR-0028: record responses visibly identify synthetic demo data."""
    clinician = _user("clinician", "clinician-0028")
    client.force_login(clinician)
    response = client.get("/api/patients/P001/")
    assert response.status_code == 200
    assert response.json()["synthetic_demo"] is True
