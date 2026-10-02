"""Ticket13: deterministic, local CDS Hooks-shaped demo boundary."""
import hashlib
import json
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.response import Response
from rest_framework import status

from . import audit
from .interaction_safety import acknowledge_evaluation, evaluate_version
from .models import (CDSCard, CDSCardAction, CDSInvocation, CDSOutboxEvent,
                     CDSRuleVersion, CDSService, InteractionRule, Patient,
                     MedicationOrderVersion)

MAX_BODY = 64 * 1024
SUPPORTED_HOOKS = {"medication-prescribe", "order-sign", "patient-view"}
INDICATORS = {"LOW", "MODERATE", "HIGH", "CRITICAL"}


def _safe_context(data):
    if not isinstance(data, dict) or len(json.dumps(data, separators=(",", ":"))) > MAX_BODY:
        raise ValueError("Bounded CDS context required")
    context = data.get("context")
    if not isinstance(context, dict):
        raise ValueError("context is required")
    patient_id = context.get("patientId")
    if not isinstance(patient_id, str) or not patient_id or len(patient_id) > 40 or any(ord(c) < 32 for c in patient_id):
        raise ValueError("bounded patient context required")
    prefetch = data.get("prefetch", {})
    if not isinstance(prefetch, dict) or len(prefetch) > 20:
        raise ValueError("prefetch is bounded")
    for value in prefetch.values():
        if len(json.dumps(value, separators=(",", ":"))) > 16 * 1024:
            raise ValueError("prefetch resource is oversized")
    return patient_id, context, prefetch


def _fingerprint(patient_id, hook, context, prefetch):
    # Fingerprints are for deduplication only and never contain the context.
    return hashlib.sha256(json.dumps({"patient": patient_id, "hook": hook, "context": context, "prefetch": prefetch}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _card_json(card):
    return {"uuid": str(card.id), "summary": card.summary, "detail": card.detail,
            "indicator": card.indicator, "source": card.source, "suggestions": card.suggestions}


def discovery():
    services = CDSService.objects.filter(active=True).order_by("id")
    return {"services": [{"id": s.id, "hook": s.hook, "title": s.title, "description": s.description, "version": s.version,
                          "prefetch": {"patient": "Patient/{{context.patientId}}"}} for s in services]}


def invoke(*, service_id, payload, actor, request_key):
    service = CDSService.objects.filter(pk=service_id, active=True).first()
    if not service or service.hook not in SUPPORTED_HOOKS:
        raise LookupError("CDS service not found")
    patient_id, context, prefetch = _safe_context(payload)
    patient = Patient.objects.filter(public_id=patient_id).first()
    if not patient:
        raise LookupError("Patient context not found")
    if not isinstance(request_key, str) or not request_key or len(request_key) > 120 or any(ord(c) < 32 for c in request_key):
        raise ValueError("bounded idempotency key required")
    fingerprint = _fingerprint(patient_id, service.hook, context, prefetch)
    with transaction.atomic():
        existing = CDSInvocation.objects.filter(service=service, request_key=request_key).first()
        if existing:
            if existing.context_fingerprint != fingerprint:
                raise ValueError("Idempotency key was already used for another request")
            return existing
        invocation = CDSInvocation.objects.create(service=service, hook=service.hook, patient=patient,
            request_key=request_key, context_fingerprint=fingerprint)
        active_rules = CDSRuleVersion.objects.filter(service=service, status=CDSRuleVersion.Status.ACTIVE).order_by("rule_key", "version")
        findings = []
        # P0 is the source of safety findings. CDS only maps those findings to cards.
        versions = list(MedicationOrderVersion.objects.filter(order__patient=patient, status=MedicationOrderVersion.Status.ACTIVE).select_related("order"))
        for version in versions:
            evaluation = evaluate_version(version=version, clinician=actor)
            findings.extend(evaluation.findings)
        for rule in active_rules:
            kind = rule.config.get("kind")
            matches = [f for f in findings if not f.get("suppressed") and f.get("kind") == kind]
            if not matches:
                continue
            severity = max((f.get("severity", "LOW") for f in matches), key={"LOW": 1, "MODERATE": 2, "HIGH": 3, "CRITICAL": 4}.get)
            detail = "Synthetic demo reminder; review the trusted medication safety evaluation."
            card = CDSCard.objects.create(invocation=invocation, rule=rule,
                summary="Allergy warning" if kind == "DRUG_ALLERGY" else "Medication interaction reminder",
                detail=detail, indicator=severity if severity in INDICATORS else "LOW",
                source={"label": "P0 medication safety data", "url": "/cds/evidence/medication-safety"},
                suggestions=[{"id": "review-medication", "label": "Review medication", "action": "review"}])
            CDSOutboxEvent.objects.create(invocation=invocation, card=card, kind="cds_card_created")
        audit.append_audit_event(actor=actor, action="create", resource_type="CDSInvocation", resource_id=invocation.pk, patient=patient)
        return invocation


def act(*, card_id, actor, action, suggestion_id="", reason=""):
    if action not in {x.value for x in CDSCardAction.Action}:
        raise ValueError("Unsupported card action")
    with transaction.atomic():
        card = CDSCard.objects.select_for_update().select_related("invocation__patient", "rule").get(pk=card_id)
        if action == "accept" and suggestion_id not in {x.get("id") for x in card.suggestions}:
            raise ValueError("Suggestion is not offered by this card")
        if action == "override" and not reason.strip():
            raise ValueError("Override reason required")
        if action == "dismiss" and card.rule.safety_critical and not reason.strip():
            raise ValueError("Dismissal reason required for safety-critical card")
        existing_action = CDSCardAction.objects.filter(card=card, actor=actor, action=action, suggestion_id=suggestion_id).first()
        if existing_action:
            return existing_action
        if action == "accept" and suggestion_id == "review-medication":
            # The card never signs or changes an order: acceptance goes through
            # the existing P0 safety service and records an acknowledgement.
            version = MedicationOrderVersion.objects.filter(order__patient=card.invocation.patient, status=MedicationOrderVersion.Status.ACTIVE).first()
            if version:
                evaluation = evaluate_version(version=version, clinician=actor)
                acknowledge_evaluation(evaluation_id=evaluation.pk, clinician=actor)
        result, _ = CDSCardAction.objects.get_or_create(card=card, actor=actor, action=action, suggestion_id=suggestion_id,
                                                        defaults={"reason": reason[:500]})
        audit.append_audit_event(actor=actor, action=action, resource_type="CDSCard", resource_id=card.pk, patient=card.invocation.patient)
        return result
