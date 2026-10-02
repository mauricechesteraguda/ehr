"""Ticket06 patient amendment workflow and immutable source boundary."""
from .logging import traced_operation
import hashlib
import json
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from . import audit
from .models import (Device, DeviceVersion, FamilyHistory, FamilyHistoryVersion,
                     MedicationOrder, MedicationOrderVersion, Patient,
                     PatientAmendment, PatientAmendmentCorrection,
                     PatientAmendmentOutbox, QuestionnaireResponse,
                     QuestionnaireResponseVersion, User)

SUPPORTED = {"Patient", "FamilyMemberHistory", "Device", "MedicationRequest", "QuestionnaireResponse"}


def _snapshot(resource_type, resource):
    if resource_type == "Patient":
        fields = ("public_id", "display_name", "race", "ethnicity", "preferred_language", "sex", "sexual_orientation", "gender_identity", "birth_date", "death_date")
        return {field: (getattr(resource, field).isoformat() if hasattr(getattr(resource, field), "isoformat") else getattr(resource, field)) for field in fields}
    if resource_type == "FamilyMemberHistory":
        fields = ("version", "relationship", "relative_sex", "relative_status", "relative_deceased", "condition_system", "condition_code", "condition_display", "submitted_display", "terminology_version", "onset_date", "recorded_date", "status")
        return {field: (getattr(resource, field).isoformat() if hasattr(getattr(resource, field), "isoformat") else getattr(resource, field)) for field in fields}
    if resource_type == "Device":
        return {"version": resource.version, "code": resource.code, "label": resource.label, "status": resource.status, "issuer": resource.issuer, "device_identifier": resource.device_identifier, "lot_number": resource.lot_number, "serial_number": resource.serial_number, "expiry_date": resource.expiry_date.isoformat() if resource.expiry_date else None, "manufacture_date": resource.manufacture_date.isoformat() if resource.manufacture_date else None}
    if resource_type == "MedicationRequest":
        return {field: str(getattr(resource, field)) for field in ("version", "medication_code", "medication_name", "dose", "dose_unit", "route", "frequency", "start_date", "quantity", "refills", "indication", "status")}
    return {"version": resource.version, "status": resource.status, "answers": resource.answers}


def _resolve(patient, resource_type, resource_id, version):
    if resource_type == "Patient":
        if str(patient.public_id) != str(resource_id) or version != 1: raise ValueError("Resource source is missing.")
        return patient
    models = {"FamilyMemberHistory": (FamilyHistoryVersion, {"history__patient": patient, "history_id": resource_id}), "Device": (DeviceVersion, {"device__patient": patient, "device_id": resource_id}), "MedicationRequest": (MedicationOrderVersion, {"order__patient": patient, "order_id": resource_id}), "QuestionnaireResponse": (QuestionnaireResponseVersion, {"response__patient": patient, "response_id": resource_id})}
    if resource_type not in models: raise ValueError("Unsupported amendment resource.")
    model, filters = models[resource_type]
    try: return model.objects.select_related().get(**filters, version=version)
    except model.DoesNotExist: raise ValueError("Resource source is missing.")


@transaction.atomic
@traced_operation
def create_amendment(*, patient, actor, resource_type, resource_id, source_version, reason, proposed_data=None, correlation_id=""):
    if actor.role != User.Role.PATIENT or patient.owner_id != actor.id: raise PermissionError("Only the patient may request an amendment.")
    reason = str(reason or "").strip()
    if not 20 <= len(reason) <= 500: raise ValueError("Reason must be between 20 and 500 characters.")
    if resource_type not in SUPPORTED: raise ValueError("Unsupported amendment resource.")
    source = _resolve(patient, resource_type, resource_id, int(source_version))
    snapshot = _snapshot(resource_type, source)
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    now = timezone.now()
    amendment = PatientAmendment.objects.create(patient=patient, requested_by=actor, resource_type=resource_type, resource_id=str(resource_id), source_version=int(source_version), source_reference=f"{resource_type}/{resource_id}/_history/{source_version}", source_checksum=hashlib.sha256(encoded).hexdigest(), source_snapshot=snapshot, proposed_data=proposed_data if isinstance(proposed_data, dict) else {}, reason=reason, submitted_at=now, due_at=now + timedelta(days=60))
    audit.append_audit_event(actor=actor, action="create", resource_type="PatientAmendment", resource_id=amendment.pk, patient=patient, correlation_id=correlation_id)
    PatientAmendmentOutbox.objects.create(amendment=amendment, kind="patient-amendment.submitted")
    return amendment


@transaction.atomic
@traced_operation
def decide_amendment(*, amendment_id, reviewer, decision, decision_reason="", correlation_id=""):
    if reviewer.role != User.Role.CLINICIAN: raise PermissionError("Clinician access required.")
    if decision not in {"accepted", "denied", "appended"}: raise ValueError("Unsupported amendment decision.")
    reason = str(decision_reason or "").strip()
    if decision in {"denied", "appended"} and not reason: raise ValueError("A decision reason is required.")
    amendment = PatientAmendment.objects.select_for_update().select_related("patient").get(pk=amendment_id)
    if amendment.status != PatientAmendment.Status.UNDER_REVIEW: raise ValueError("Amendment is not under review.")
    source = _resolve(amendment.patient, amendment.resource_type, amendment.resource_id, amendment.source_version)
    current = {"Patient": 1}.get(amendment.resource_type)
    if amendment.resource_type == "FamilyMemberHistory": current = source.history.active_version.version if source.history.active_version_id else None
    elif amendment.resource_type == "Device": current = source.device.active_version.version if source.device.active_version_id else None
    elif amendment.resource_type == "MedicationRequest": current = source.order.active_version.version if source.order.active_version_id else None
    elif amendment.resource_type == "QuestionnaireResponse": current = source.response.active_version.version if source.response.active_version_id else None
    if current != amendment.source_version: raise ValueError("Amendment source is stale.")
    if _snapshot(amendment.resource_type, source) != amendment.source_snapshot: raise ValueError("Amendment source is stale.")
    amendment.reviewer = reviewer; amendment.decision_reason = reason; amendment.decided_at = timezone.now(); amendment.status = decision
    if decision == "appended": amendment.addendum = {"source_reference": amendment.source_reference, "source_version": amendment.source_version, "proposed_data": amendment.proposed_data}
    if decision == "accepted":
        data = {**amendment.source_snapshot, **amendment.proposed_data}
        next_version = amendment.source_version + 1
        if amendment.resource_type == "FamilyMemberHistory":
            history = FamilyHistory.objects.get(pk=amendment.resource_id, patient=amendment.patient)
            source_version = FamilyHistoryVersion.objects.get(history=history, version=amendment.source_version)
            new_version = FamilyHistoryVersion.objects.create(history=history, version=next_version, relationship=data.get("relationship", source_version.relationship), relative_sex=data.get("relative_sex", source_version.relative_sex), relative_status=data.get("relative_status", source_version.relative_status), relative_deceased=data.get("relative_deceased", source_version.relative_deceased), condition_system=data.get("condition_system", source_version.condition_system), condition_code=data.get("condition_code", source_version.condition_code), condition_display=data.get("condition_display", source_version.condition_display), submitted_display=data.get("submitted_display", source_version.submitted_display), terminology_version=data.get("terminology_version", source_version.terminology_version), onset_date=data.get("onset_date") or source_version.onset_date, recorded_date=data.get("recorded_date") or source_version.recorded_date, status="active", supersedes=source_version, created_by=reviewer)
            history.active_version = new_version; history.save(update_fields=["active_version"])
        PatientAmendmentCorrection.objects.create(amendment=amendment, resource_type=amendment.resource_type, resource_id=amendment.resource_id, version=next_version, data=data, supersedes_version=amendment.source_version)
        amendment.accepted_version = next_version
    amendment.save(update_fields=["status", "reviewer", "decision_reason", "decided_at", "addendum", "accepted_version"])
    audit.append_audit_event(actor=reviewer, action="update", resource_type="PatientAmendment", resource_id=amendment.pk, patient=amendment.patient, correlation_id=correlation_id)
    PatientAmendmentOutbox.objects.create(amendment=amendment, kind=f"patient-amendment.{decision}")
    return amendment


@transaction.atomic
@traced_operation
def begin_review(*, amendment_id, reviewer):
    if reviewer.role != User.Role.CLINICIAN: raise PermissionError("Clinician access required.")
    item = PatientAmendment.objects.select_for_update().get(pk=amendment_id)
    if item.status != PatientAmendment.Status.SUBMITTED: raise ValueError("Amendment is not submitted.")
    item.status = PatientAmendment.Status.UNDER_REVIEW; item.reviewer = reviewer; item.save(update_fields=["status", "reviewer"])
    return item


@transaction.atomic
@traced_operation
def dispatch_amendment_outbox(*, event_id, delivered):
    """Deterministic notification retry state machine; only lifecycle metadata is retained."""
    event = PatientAmendmentOutbox.objects.select_for_update().get(pk=event_id)
    if event.state == PatientAmendmentOutbox.State.SENT: return event
    event.attempts += 1
    if delivered:
        event.state = PatientAmendmentOutbox.State.SENT; event.sent_at = timezone.now(); event.last_error_code = ""
    elif event.attempts >= 3:
        event.state = PatientAmendmentOutbox.State.FAILED; event.last_error_code = "delivery_failed"
    else:
        event.state = PatientAmendmentOutbox.State.RETRY; event.last_error_code = "delivery_failed"; event.next_attempt_at = timezone.now() + timedelta(minutes=2 ** event.attempts)
    event.save(update_fields=["attempts", "state", "sent_at", "last_error_code", "next_attempt_at"])
    return event
