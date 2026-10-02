"""Ticket03 expansion evidence mapped to CSV TC-EXP-0011..0015."""
import pytest


def _user(role, username):
    from django.contrib.auth import get_user_model
    return get_user_model().objects.create_user(username=username, password="safe", role=role)


@pytest.mark.django_db
def test_TC_EXP_0011_add_coded_family_history(client):
    """TC-EXP-0011: clinician can add an approved synthetic coded entry."""
    from backend.users.models import Patient
    from datetime import date
    clinician = _user("clinician", "ticket03-0011")
    Patient.objects.create(public_id="T0311", display_name="Synthetic", birth_date=date(1980, 1, 1))
    client.force_login(clinician)
    response = client.post("/api/patients/T0311/family-history/", {"relationship": "mother", "relative_sex": "female", "relative_status": "deceased", "relative_deceased": True, "condition_system": "http://snomed.info/sct", "condition_code": "IHD-001", "condition_display": "Synthetic ischemic heart disease"}, content_type="application/json")
    assert response.status_code == 201


@pytest.mark.django_db
def test_TC_EXP_0012_family_history_validation_is_fail_closed(client):
    """TC-EXP-0012: unresolved terminology produces no persisted entry."""
    from backend.users.models import Patient, FamilyHistory
    from datetime import date
    clinician = _user("clinician", "ticket03-0012")
    Patient.objects.create(public_id="T0312", display_name="Synthetic", birth_date=date(1980, 1, 1))
    client.force_login(clinician)
    response = client.post("/api/patients/T0312/family-history/", {"relationship": "", "condition_system": "http://snomed.info/sct", "condition_code": "NOT-CODE", "condition_display": "Guess"}, content_type="application/json")
    assert response.status_code == 400 and FamilyHistory.objects.count() == 0


@pytest.mark.django_db
def test_TC_EXP_0013_update_is_immutable_and_delete_is_rejected(client):
    """TC-EXP-0013: corrections append a version and destructive deletion is unavailable."""
    from backend.users.models import FamilyHistory, FamilyHistoryVersion, Patient
    from datetime import date
    clinician = _user("clinician", "ticket03-0013")
    patient = Patient.objects.create(public_id="T0313", display_name="Synthetic", birth_date=date(1980, 1, 1))
    history = FamilyHistory.objects.create(patient=patient)
    version = FamilyHistoryVersion.objects.create(history=history, version=1, relationship="mother", condition_system="http://snomed.info/sct", condition_code="IHD-001", condition_display="Synthetic ischemic heart disease", created_by=clinician)
    history.active_version = version; history.save(update_fields=["active_version"])
    client.force_login(clinician)
    response = client.delete(f"/api/patients/{patient.public_id}/family-history/{history.pk}/")
    assert response.status_code == 405
    with pytest.raises(ValueError):
        version.delete()


@pytest.mark.django_db
def test_TC_EXP_0014_family_history_role_restriction(client):
    """TC-EXP-0014: patient self-read does not grant mutation or cross-patient access."""
    patient = _user("patient", "ticket03-0014")
    client.force_login(patient)
    assert client.post("/api/patients/P002/family-history/", {}, content_type="application/json").status_code in {403, 404}


@pytest.mark.django_db
def test_TC_EXP_0015_family_history_empty_no_result(client):
    """TC-EXP-0015: empty authorized collection is explicit and bounded."""
    clinician = _user("clinician", "ticket03-0015")
    client.force_login(clinician)
    response = client.get("/api/patients/P002/family-history/?code=rare-code")
    assert response.status_code == 200 and response.json() == []
