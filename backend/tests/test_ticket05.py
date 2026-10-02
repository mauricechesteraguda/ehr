"""type-10022026-Maurice: Ticket 05 acceptance coverage; synthetic data only.

Required evidence: evaluation persistence, floor boundaries, acknowledgement gating,
critical blocking, stale recomputation, fail-closed dependencies, immutable evidence,
administrative boundaries, safe UI/API states, and concurrent atomic signing.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest


def _user(role, username):
    """type-10022026-Maurice: Create a disposable test principal without clinical data."""
    from django.contrib.auth import get_user_model
    return get_user_model().objects.create_user(username=username, password="safe", role=role)


def _draft(clinician, suffix):
    """type-10022026-Maurice: Build one isolated synthetic patient/order/draft tuple."""
    from backend.users.models import MedicationOrder, MedicationOrderVersion, Patient
    patient = Patient.objects.create(
        public_id=f"T{suffix}", display_name="Synthetic Test Patient", birth_date=date(1980, 1, 1)
    )
    order = MedicationOrder.objects.create(patient=patient, prescriber=clinician)
    version = MedicationOrderVersion.objects.create(
        order=order, version=1, created_by=clinician, medication_code="MED-A",
        medication_name="Synthetic A", dose=1, dose_unit="mg", route="oral",
        frequency="daily", start_date=date(2026, 1, 1), quantity=10, refills=1,
        indication="Synthetic indication", status=MedicationOrderVersion.Status.DRAFT,
    )
    order.active_version = version
    order.save(update_fields=["active_version"])
    return patient, order, version


def _rule(**values):
    """type-10022026-Maurice: Persist one synthetic active safety rule."""
    from backend.users.models import InteractionRule
    return InteractionRule.objects.create(**values)


@pytest.mark.django_db
def test_TC_EHR_0054_drug_drug_evaluation_is_persisted():
    """TC-EHR-0054: active drug-drug severity is returned and immutably persisted."""
    from backend.users.interaction_safety import evaluate_version
    from backend.users.models import InteractionEvaluation, MedicationOrderVersion
    clinician = _user("clinician", "clinician-0054")
    _, _, version = _draft(clinician, "054")
    active = MedicationOrderVersion.objects.create(order=version.order, version=2, created_by=clinician, medication_code="MED-B", medication_name="Synthetic B", dose=1, dose_unit="mg", route="oral", frequency="daily", start_date=date(2026, 1, 1), quantity=1, indication="active", status=MedicationOrderVersion.Status.ACTIVE)
    version.order.active_version = active
    version.order.save(update_fields=["active_version"])
    _rule(kind="DRUG_DRUG", medication_code="MED-A", related_medication_code="MED-B", severity="HIGH")
    evaluation = evaluate_version(version=version, clinician=clinician)
    assert evaluation.pk and evaluation.findings[0]["severity"] == "HIGH"
    assert InteractionEvaluation.objects.filter(pk=evaluation.pk).exists()


@pytest.mark.django_db
def test_TC_EHR_0055_drug_allergy_evaluation_matches_only_active_allergy():
    """TC-EHR-0055: matching allergy is present; unrelated allergy is absent."""
    from backend.users.interaction_safety import evaluate_version
    from backend.users.models import AllergyIntolerance
    clinician = _user("clinician", "clinician-0055")
    patient, _, version = _draft(clinician, "055")
    AllergyIntolerance.objects.create(patient=patient, code="ALLERGY-X", label="Synthetic allergy")
    _rule(kind="DRUG_ALLERGY", medication_code="MED-A", allergy_code="ALLERGY-X", severity="MODERATE")
    _rule(kind="DRUG_ALLERGY", medication_code="MED-A", allergy_code="ALLERGY-NO", severity="HIGH")
    evaluation = evaluate_version(version=version, clinician=clinician)
    assert len(evaluation.findings) == 1 and evaluation.findings[0]["severity"] == "MODERATE"


@pytest.mark.django_db
def test_TC_EHR_0056_floor_suppresses_noncritical_but_not_critical():
    """TC-EHR-0056: below-floor noncritical findings suppress while critical remains visible."""
    from backend.users.interaction_safety import evaluate_version
    from backend.users.models import AlertConfiguration, MedicationOrderVersion
    clinician = _user("clinician", "clinician-0056")
    _, order, version = _draft(clinician, "056")
    active = MedicationOrderVersion.objects.create(order=order, version=2, created_by=clinician, medication_code="MED-B", medication_name="B", dose=1, dose_unit="mg", route="oral", frequency="daily", start_date=date(2026, 1, 1), quantity=1, indication="active", status="active")
    order.active_version = active; order.save(update_fields=["active_version"])
    AlertConfiguration.objects.create(severity_floor="HIGH")
    _rule(kind="DRUG_DRUG", medication_code="MED-A", related_medication_code="MED-B", severity="LOW")
    _rule(kind="DRUG_DRUG", medication_code="MED-A", related_medication_code="MED-B", severity="CRITICAL")
    evaluation = evaluate_version(version=version, clinician=clinician)
    assert {finding["suppressed"] for finding in evaluation.findings} == {False, True}


@pytest.mark.django_db
def test_TC_EHR_0057_acknowledgement_gate_allows_noncritical_signing():
    """TC-EHR-0057: visible noncritical finding requires and then accepts acknowledgement."""
    from backend.users.interaction_safety import acknowledge_evaluation, evaluate_version, sign_version
    from backend.users.models import AllergyIntolerance
    clinician = _user("clinician", "clinician-0057")
    patient, order, version = _draft(clinician, "057")
    AllergyIntolerance.objects.create(patient=patient, code="ALLERGY-57", label="Synthetic allergy")
    _rule(kind="DRUG_ALLERGY", medication_code="MED-A", allergy_code="ALLERGY-57", severity="MODERATE")
    evaluation = evaluate_version(version=version, clinician=clinician)
    with pytest.raises(PermissionError, match="acknowledgement"):
        sign_version(order_id=order.pk, clinician=clinician, evaluation_id=evaluation.pk)
    acknowledge_evaluation(evaluation_id=evaluation.pk, clinician=clinician)
    signed, _ = sign_version(order_id=order.pk, clinician=clinician, evaluation_id=evaluation.pk)
    assert signed.status == "active" and order.__class__.objects.get(pk=order.pk).active_version_id == signed.pk


@pytest.mark.django_db
def test_TC_EHR_0058_critical_finding_blocks_signing():
    """TC-EHR-0058: critical finding blocks signing regardless of acknowledgement."""
    from backend.users.interaction_safety import acknowledge_evaluation, evaluate_version, sign_version
    from backend.users.models import AllergyIntolerance
    clinician = _user("clinician", "clinician-0058")
    patient, order, version = _draft(clinician, "058")
    AllergyIntolerance.objects.create(patient=patient, code="ALLERGY-58", label="Synthetic allergy")
    _rule(kind="DRUG_ALLERGY", medication_code="MED-A", allergy_code="ALLERGY-58", severity="CRITICAL")
    evaluation = evaluate_version(version=version, clinician=clinician)
    acknowledge_evaluation(evaluation_id=evaluation.pk, clinician=clinician)
    with pytest.raises(PermissionError, match="Critical"):
        sign_version(order_id=order.pk, clinician=clinician, evaluation_id=evaluation.pk, acknowledgement=True)
    assert order.__class__.objects.get(pk=order.pk).active_version_id == version.pk


@pytest.mark.django_db
def test_TC_EHR_0059_stale_evaluation_is_recomputed_before_signing():
    """TC-EHR-0059: rule revision invalidates old evidence and creates fresh evidence."""
    from backend.users.interaction_safety import acknowledge_evaluation, evaluate_version, sign_version
    from backend.users.models import AllergyIntolerance
    from backend.users.models import InteractionEvaluation
    clinician = _user("clinician", "clinician-0059")
    patient, order, version = _draft(clinician, "059")
    AllergyIntolerance.objects.create(patient=patient, code="ALLERGY-59", label="Synthetic allergy")
    rule = _rule(kind="DRUG_ALLERGY", medication_code="MED-A", allergy_code="ALLERGY-59", severity="MODERATE")
    old = evaluate_version(version=version, clinician=clinician)
    rule.active = False; rule.save(update_fields=["active", "updated_at"])
    acknowledge_evaluation(evaluation_id=old.pk, clinician=clinician)
    signed, fresh = sign_version(order_id=order.pk, clinician=clinician, evaluation_id=old.pk)
    assert signed.status == "active" and fresh.pk != old.pk
    assert InteractionEvaluation.objects.filter(medication_version=version).count() == 2


@pytest.mark.django_db(transaction=True)
def test_TC_EHR_0060_dependency_failure_fails_closed_and_rolls_back_audit():
    """TC-EHR-0060: evaluator/audit failures leave no activation or false audit success."""
    from backend.users import audit
    from backend.users import interaction_safety
    from backend.users.models import AuditEvent
    clinician = _user("clinician", "clinician-0060")
    _, order, version = _draft(clinician, "060")
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(interaction_safety, "evaluate_version", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("evaluator unavailable")))
    with pytest.raises(RuntimeError):
        interaction_safety.sign_version(order_id=order.pk, clinician=clinician)
    monkeypatch.undo()
    monkeypatch.setattr(audit, "append_audit_event", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("audit unavailable")))
    with pytest.raises(RuntimeError):
        interaction_safety.sign_version(order_id=order.pk, clinician=clinician)
    monkeypatch.undo()
    assert order.__class__.objects.get(pk=order.pk).active_version_id == version.pk
    assert not AuditEvent.objects.filter(resource_id=str(order.pk), action="sign").exists()

    def attempt():
        try:
            interaction_safety.sign_version(order_id=order.pk, clinician=clinician)
            return "signed"
        except Exception as error:
            return type(error).__name__

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: attempt(), range(2)))
    assert outcomes.count("signed") == 1
    assert AuditEvent.objects.filter(resource_id=str(order.pk), action="sign").count() == 1


@pytest.mark.django_db
def test_TC_EHR_0061_safety_evidence_is_immutable():
    """TC-EHR-0061: evaluation and acknowledgement updates/deletes are rejected."""
    from backend.users.interaction_safety import acknowledge_evaluation, evaluate_version
    clinician = _user("clinician", "clinician-0061")
    _, _, version = _draft(clinician, "061")
    evaluation = evaluate_version(version=version, clinician=clinician)
    ack = acknowledge_evaluation(evaluation_id=evaluation.pk, clinician=clinician)
    with pytest.raises(ValueError):
        evaluation.save(update_fields=["floor"])
    with pytest.raises(ValueError):
        ack.delete()


@pytest.mark.django_db
def test_TC_EHR_0062_admin_rule_and_floor_boundaries():
    """TC-EHR-0062: only admins change rules/floors and invalid floor does not mutate."""
    admin = _user("admin", "admin-0062")
    clinician = _user("clinician", "clinician-0062")
    from django.test import Client
    client = Client(); client.force_login(clinician)
    assert client.post("/api/admin/interaction-rules/", {"severity_floor": "HIGH"}).status_code == 403
    client.force_login(admin)
    assert client.post("/api/admin/interaction-rules/", {"severity_floor": "INVALID"}).status_code == 400
    assert client.post("/api/admin/interaction-rules/", {"severity_floor": "HIGH"}).json()["severity_floor"] == "HIGH"
    assert client.post("/api/admin/interaction-rules/", {"kind": "DRUG_DRUG", "medication_code": "MED-A", "related_medication_code": "MED-B", "severity": "LOW"}).status_code == 201


@pytest.mark.django_db
def test_TC_EHR_0063_clinician_alert_and_retry_states_fail_safe(client):
    """TC-EHR-0063: API exposes safe evaluate/sign failure states without activation."""
    clinician = _user("clinician", "clinician-0063")
    patient, order, version = _draft(clinician, "063")
    client.force_login(clinician)
    response = client.post(f"/api/patients/{patient.public_id}/medications/{order.pk}/evaluate/")
    assert response.status_code == 200 and "id" in response.json()
    from backend.users import interaction_safety
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(interaction_safety, "evaluate_version", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("dependency unavailable")))
    version.status = "draft"
    response = client.post(f"/api/patients/{patient.public_id}/medications/{order.pk}/sign/", {})
    monkeypatch.undo()
    assert response.status_code in {409, 503}
    assert order.__class__.objects.get(pk=order.pk).active_version_id == version.pk
