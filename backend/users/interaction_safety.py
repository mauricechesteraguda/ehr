"""type-10022026-Maurice: Fail-closed synthetic medication safety evaluation."""
import hashlib
import json
from datetime import timezone

from django.db import transaction
from django.utils import timezone as django_timezone

from .logging import log_event
from .models import (AlertConfiguration, AllergyIntolerance, InteractionAcknowledgement,
                     InteractionEvaluation, InteractionRule, MedicationOrder, MedicationOrderVersion)
from .tracing import trace_function

_RANK = {"LOW": 1, "MODERATE": 2, "HIGH": 3, "CRITICAL": 4}


@trace_function
def _configuration():
    """type-10022026-Maurice: Read the single safety floor, creating a safe LOW default."""
    return AlertConfiguration.objects.get_or_create(singleton=True, defaults={"severity_floor": "LOW"})[0]


@trace_function
def _rule_active(rule, now):
    """type-10022026-Maurice: Apply active and effective-date boundaries without exposing payloads."""
    return rule.active and (rule.effective_from is None or rule.effective_from <= now) and (rule.effective_to is None or rule.effective_to >= now)


@trace_function
def evaluate_version(*, version, clinician):
    """type-10022026-Maurice: Evaluate active medicines/allergies and persist immutable evidence."""
    now = django_timezone.now()
    configuration = _configuration()
    rules = [rule for rule in InteractionRule.objects.all() if _rule_active(rule, now)]
    active_codes = set(MedicationOrderVersion.objects.filter(order__patient=version.order.patient, status=MedicationOrderVersion.Status.ACTIVE).exclude(pk=version.pk).values_list("medication_code", flat=True))
    allergy_codes = set(AllergyIntolerance.objects.filter(patient=version.order.patient).values_list("code", flat=True))
    findings = []
    for rule in rules:
        matched = ((rule.kind == InteractionRule.Kind.DRUG_DRUG and rule.medication_code == version.medication_code and rule.related_medication_code in active_codes) or
                   (rule.kind == InteractionRule.Kind.DRUG_DRUG and rule.related_medication_code == version.medication_code and rule.medication_code in active_codes) or
                   (rule.kind == InteractionRule.Kind.DRUG_ALLERGY and rule.medication_code == version.medication_code and rule.allergy_code in allergy_codes))
        if matched:
            visible = rule.severity == InteractionRule.Severity.CRITICAL or _RANK[rule.severity] >= _RANK[configuration.severity_floor]
            findings.append({"rule_id": rule.pk, "kind": rule.kind, "severity": rule.severity, "description": rule.description, "suppressed": not visible})
    fingerprint = hashlib.sha256(json.dumps({"version": version.pk, "rules": [(r.pk, r.updated_at.isoformat() if r.updated_at else None) for r in rules], "floor": configuration.severity_floor}, sort_keys=True).encode()).hexdigest()
    return InteractionEvaluation.objects.create(medication_version=version, evaluated_at=now, fingerprint=fingerprint, floor=configuration.severity_floor, findings=findings, created_by=clinician)


@trace_function
def evaluation_is_stale(evaluation):
    """type-10022026-Maurice: Reject evidence if rules, floor, or medication context changed."""
    configuration = _configuration()
    now = django_timezone.now()
    rules = [rule for rule in InteractionRule.objects.all() if _rule_active(rule, now)]
    expected = hashlib.sha256(json.dumps({"version": evaluation.medication_version_id, "rules": [(r.pk, r.updated_at.isoformat() if r.updated_at else None) for r in rules], "floor": configuration.severity_floor}, sort_keys=True).encode()).hexdigest()
    return expected != evaluation.fingerprint


@trace_function
def sign_version(*, order_id, clinician, evaluation_id=None, acknowledgement=False, correlation_id=""):
    """type-10022026-Maurice: Re-evaluate stale drafts and atomically activate plus audit."""
    try:
        with transaction.atomic():
            # type-10022026-Maurice: Lock only the non-nullable order row. PostgreSQL
            # rejects FOR UPDATE when select_related adds the nullable active_version
            # outer join; the order lock still serializes pointer changes and keeps
            # evaluation, activation, and audit in one transaction.
            order = MedicationOrder.objects.select_for_update().get(pk=order_id)
            version = MedicationOrderVersion.objects.get(pk=order.active_version_id) if order.active_version_id else None
            if version is None or version.status != MedicationOrderVersion.Status.DRAFT:
                raise ValueError("Only a draft medication can be signed")
            evaluation = InteractionEvaluation.objects.filter(pk=evaluation_id, medication_version=version).first() if evaluation_id else None
            if evaluation is None or evaluation_is_stale(evaluation):
                evaluation = evaluate_version(version=version, clinician=clinician)
            visible = [finding for finding in evaluation.findings if not finding.get("suppressed")]
            critical = [finding for finding in visible if finding.get("severity") == "CRITICAL"]
            if critical:
                raise PermissionError("Critical interaction blocks signing")
            if visible and not InteractionAcknowledgement.objects.filter(evaluation=evaluation, clinician=clinician).exists():
                raise PermissionError("Clinician acknowledgement required")
            version = MedicationOrderVersion.objects.create(
                order=order, version=version.version + 1, supersedes=version,
                created_by=clinician, status=MedicationOrderVersion.Status.ACTIVE,
                medication_code=version.medication_code, medication_name=version.medication_name,
                dose=version.dose, dose_unit=version.dose_unit, route=version.route,
                frequency=version.frequency, start_date=version.start_date, quantity=version.quantity,
                refills=version.refills, indication=version.indication,
            )
            order.active_version = version
            order.save(update_fields=["active_version"])
            from . import audit
            audit.append_audit_event(actor=clinician, action="sign", resource_type="MedicationOrder", resource_id=order.pk, patient=order.patient, correlation_id=correlation_id)
            log_event("medication.sign.success", outcome="success", component="medication", operation="sign")
            return version, evaluation
    except Exception as error:
        log_event("medication.sign.failure", outcome="failure", component="medication", operation="sign", exception=error)
        raise


@trace_function
def acknowledge_evaluation(*, evaluation_id, clinician):
    """type-10022026-Maurice: Record one immutable clinician acknowledgement."""
    return InteractionAcknowledgement.objects.create(evaluation_id=evaluation_id, clinician=clinician, acknowledged_at=django_timezone.now())
