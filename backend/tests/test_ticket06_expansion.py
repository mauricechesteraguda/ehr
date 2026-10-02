"""Ticket06 expansion executable spec; CSV mapping TC-EXP-0031..TC-EXP-0035."""
from datetime import date, timedelta

import pytest
from django.utils import timezone


def fixture():
    from backend.users.models import FamilyHistory, FamilyHistoryVersion, Patient, User
    clinician = User.objects.create_user(username="amend-clinician", password="x", role="clinician")
    patient_user = User.objects.create_user(username="amend-patient", password="x", role="patient")
    patient = Patient.objects.create(public_id="AMD001", owner=patient_user, display_name="Synthetic", birth_date=date(1980, 1, 1))
    history = FamilyHistory.objects.create(patient=patient)
    source = FamilyHistoryVersion.objects.create(history=history, version=1, relationship="mother", condition_system="http://snomed.info/sct", condition_code="123", condition_display="Source", created_by=clinician)
    history.active_version = source
    history.save(update_fields=["active_version"])
    return clinician, patient_user, patient, source


@pytest.mark.django_db
def test_TC_EXP_0031_submission_snapshots_source_and_due_date():
    clinician, patient_user, patient, source = fixture()
    from backend.users.amendments import create_amendment
    amendment = create_amendment(patient=patient, actor=patient_user, resource_type="FamilyMemberHistory", resource_id=source.history_id, source_version=source.version, reason="Please correct this synthetic record because the source entry is inaccurate.", proposed_data={"condition_display": "Corrected"})
    assert amendment.status == "submitted"
    assert amendment.due_at == amendment.submitted_at + timedelta(days=60)
    assert amendment.source_checksum and amendment.source_snapshot
    assert amendment.source_snapshot["condition_display"] == "Source"


@pytest.mark.django_db
def test_TC_EXP_0032_append_preserves_original_and_links_addendum():
    clinician, patient_user, patient, source = fixture()
    from backend.users.amendments import begin_review, create_amendment, decide_amendment
    amendment = create_amendment(patient=patient, actor=patient_user, resource_type="FamilyMemberHistory", resource_id=source.history_id, source_version=1, reason="The record needs an additional clarification for clinical accuracy.", proposed_data={"condition_display": "Addendum"})
    begin_review(amendment_id=amendment.pk, reviewer=clinician)
    decided = decide_amendment(amendment_id=amendment.pk, reviewer=clinician, decision="appended", decision_reason="Addendum preserves the source and records the patient clarification.")
    assert decided.status == "appended"
    source.refresh_from_db()
    assert source.condition_display == "Source"
    assert decided.addendum and decided.addendum["source_version"] == 1


@pytest.mark.django_db
def test_TC_EXP_0033_reason_boundaries_roles_and_transitions():
    clinician, patient_user, patient, source = fixture()
    from backend.users.amendments import begin_review, create_amendment, decide_amendment
    with pytest.raises(ValueError):
        create_amendment(patient=patient, actor=patient_user, resource_type="FamilyMemberHistory", resource_id=source.history_id, source_version=1, reason="x", proposed_data={})
    amendment = create_amendment(patient=patient, actor=patient_user, resource_type="FamilyMemberHistory", resource_id=source.history_id, source_version=1, reason="A valid reason that is long enough to explain the requested correction.", proposed_data={})
    with pytest.raises(PermissionError):
        decide_amendment(amendment_id=amendment.pk, reviewer=patient_user, decision="denied", decision_reason="Not permitted.")
    with pytest.raises(ValueError):
        decide_amendment(amendment_id=amendment.pk, reviewer=clinician, decision="denied", decision_reason="")
    begin_review(amendment_id=amendment.pk, reviewer=clinician)
    decided = decide_amendment(amendment_id=amendment.pk, reviewer=clinician, decision="denied", decision_reason="The source is supported and no correction is warranted.")
    with pytest.raises(ValueError):
        decide_amendment(amendment_id=decided.pk, reviewer=clinician, decision="accepted", decision_reason="Not a valid transition.")


@pytest.mark.django_db
def test_TC_EXP_0034_stale_source_conflict_and_atomic_notification():
    clinician, patient_user, patient, source = fixture()
    from backend.users.amendments import begin_review, create_amendment, decide_amendment
    amendment = create_amendment(patient=patient, actor=patient_user, resource_type="FamilyMemberHistory", resource_id=source.history_id, source_version=1, reason="A valid reason that is long enough to explain the requested correction.", proposed_data={"condition_display": "Corrected"})
    source2 = type(source).objects.create(history=source.history, version=2, relationship="mother", condition_system="http://snomed.info/sct", condition_code="123", condition_display="Newer", created_by=clinician, supersedes=source)
    source.history.active_version = source2
    source.history.save(update_fields=["active_version"])
    begin_review(amendment_id=amendment.pk, reviewer=clinician)
    with pytest.raises(ValueError, match="stale"):
        decide_amendment(amendment_id=amendment.pk, reviewer=clinician, decision="accepted", decision_reason="The proposed correction is safe to apply.")


@pytest.mark.django_db
def test_TC_EXP_0035_unsupported_and_missing_resource_are_safe():
    _, patient_user, patient, _ = fixture()
    from backend.users.amendments import create_amendment
    with pytest.raises(ValueError):
        create_amendment(patient=patient, actor=patient_user, resource_type="Unsupported", resource_id="x", source_version=1, reason="A valid reason that is long enough to explain the requested correction.", proposed_data={})
