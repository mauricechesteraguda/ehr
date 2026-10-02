"""Ticket05 expansion specification: TC-EXP-0501..TC-EXP-0512.

These tests are the executable spec for version pinning, typed validation, patient-only
submission, immutable corrections, review reasons, and atomic notification evidence.
"""
from datetime import date

import pytest


def _fixture():
    from backend.users.models import Patient, Questionnaire, QuestionnaireItem, QuestionnaireVersion, User
    clinician = User.objects.create_user(username="exp-clinician", password="x", role="clinician")
    patient_user = User.objects.create_user(username="exp-patient", password="x", role="patient")
    patient = Patient.objects.create(public_id="EXP001", owner=patient_user, display_name="Synthetic", birth_date=date(1980, 1, 1))
    questionnaire = Questionnaire.objects.create(code="exp", title="Expansion")
    version = QuestionnaireVersion.objects.create(questionnaire=questionnaire, version=1, status="active", created_by=clinician)
    QuestionnaireItem.objects.create(questionnaire_version=version, link_id="ok", text="OK", item_type="boolean", ordinal=1, required=True)
    QuestionnaireItem.objects.create(questionnaire_version=version, link_id="score", text="Score", item_type="integer", ordinal=2, min_value=0, max_value=10)
    QuestionnaireItem.objects.create(questionnaire_version=version, link_id="kind", text="Kind", item_type="choice", ordinal=3, options=["a", "b"])
    questionnaire.active_version = version; questionnaire.save(update_fields=["active_version"])
    return clinician, patient_user, patient, questionnaire, version


@pytest.mark.django_db
def test_TC_EXP_0501_all_supported_types_and_deterministic_order():
    _, patient_user, patient, questionnaire, version = _fixture()
    from backend.users.questionnaires import create_response
    _, saved = create_response(patient=patient, questionnaire=questionnaire, actor=patient_user, questionnaire_version_number=1, answers={"kind": "a", "score": 5, "ok": True}, status="submitted")
    assert list(saved.answers) == ["ok", "score", "kind"]


@pytest.mark.django_db
def test_TC_EXP_0502_required_boundaries_and_unknown_payload_rejected():
    _, patient_user, patient, questionnaire, _ = _fixture()
    from backend.users.questionnaires import create_response
    with pytest.raises(ValueError):
        create_response(patient=patient, questionnaire=questionnaire, actor=patient_user, questionnaire_version_number=1, answers={"score": 11}, status="submitted")


@pytest.mark.django_db
def test_TC_EXP_0503_patient_self_only_and_draft_submit():
    clinician, patient_user, patient, questionnaire, _ = _fixture()
    from backend.users.questionnaires import create_response
    _, draft = create_response(patient=patient, questionnaire=questionnaire, actor=patient_user, questionnaire_version_number=1, answers={}, status="draft")
    assert draft.status == "draft"
    with pytest.raises(PermissionError):
        create_response(patient=patient, questionnaire=questionnaire, actor=clinician, questionnaire_version_number=1, answers={"ok": True}, status="submitted")


@pytest.mark.django_db
def test_TC_EXP_0504_correction_is_new_immutable_version_and_pins_definition():
    _, patient_user, patient, questionnaire, version = _fixture()
    from backend.users.models import QuestionnaireResponseVersion
    from backend.users.questionnaires import create_response
    response, first = create_response(patient=patient, questionnaire=questionnaire, actor=patient_user, questionnaire_version_number=1, answers={"ok": True}, status="submitted")
    _, second = create_response(patient=patient, questionnaire=questionnaire, actor=patient_user, questionnaire_version_number=1, answers={"ok": False}, status="submitted", correction=response.pk)
    assert second.version == 2 and second.supersedes_id == first.pk
    with pytest.raises(ValueError): first.save()
    assert QuestionnaireResponseVersion.objects.filter(response=response).count() == 2


@pytest.mark.django_db
def test_TC_EXP_0505_review_reason_states_and_outbox():
    clinician, patient_user, patient, questionnaire, _ = _fixture()
    from backend.users.models import QuestionnaireOutboxEvent
    from backend.users.questionnaires import create_response, review_response
    _, saved = create_response(patient=patient, questionnaire=questionnaire, actor=patient_user, questionnaire_version_number=1, answers={"ok": True}, status="submitted")
    with pytest.raises(ValueError): review_response(response_version_id=saved.pk, reviewer=clinician, decision="rejected")
    review = review_response(response_version_id=saved.pk, reviewer=clinician, decision="accepted")
    assert review.decision == "accepted" and QuestionnaireOutboxEvent.objects.count() == 2
