"""type-10022026-Maurice: Central fail-closed emergency read authorization."""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from . import audit
from .models import ClinicianPatientAssignment, EmergencyAccessOutboxEvent, EmergencyAccessRequest, Patient, User

GRANT_MINUTES = 30


def normal_patient_access(patient, user):
    """type-10022026-Maurice: Emergency access never replaces normal policy."""
    if user.role == User.Role.PATIENT:
        return patient.owner_id == user.id
    if user.role == User.Role.ADMIN:
        return True
    if user.role != User.Role.CLINICIAN:
        return False
    return not patient.restricted_access or ClinicianPatientAssignment.objects.filter(clinician=user, patient=patient).exists()


def active_grant(patient, user, *, at=None):
    at = at or timezone.now()
    grant = EmergencyAccessRequest.objects.filter(clinician=user, patient=patient, state=EmergencyAccessRequest.State.ACTIVE).order_by("-requested_at").first()
    if grant and grant.expires_at > at:
        return grant
    return None


def can_read(patient, user, *, request=None):
    """type-10022026-Maurice: GET-only break-glass fallback; writes must not pass request."""
    if normal_patient_access(patient, user):
        return True
    return bool(request is not None and request.method == "GET" and user.role == User.Role.CLINICIAN and active_grant(patient, user))


@transaction.atomic
def request_access(*, clinician, patient, justification, correlation_id=""):
    """type-10022026-Maurice: Persist grant, audit, and notification intent as one unit."""
    if clinician.role != User.Role.CLINICIAN or not clinician.is_active:
        raise PermissionError("Active clinician required")
    if not isinstance(justification, str) or not 20 <= len(justification) <= 500:
        raise ValueError("Justification must be 20 to 500 characters")
    now = timezone.now()
    grant = EmergencyAccessRequest.objects.create(clinician=clinician, patient=patient, justification=justification, requested_at=now, expires_at=now + timedelta(minutes=GRANT_MINUTES))
    audit.append_audit_event(actor=clinician, action="request", resource_type="EmergencyAccessRequest", resource_id=grant.pk, patient=patient, correlation_id=correlation_id)
    audit.append_audit_event(actor=clinician, action="grant", resource_type="EmergencyAccessRequest", resource_id=grant.pk, patient=patient, correlation_id=correlation_id)
    EmergencyAccessOutboxEvent.objects.create(request=grant)
    return grant


@transaction.atomic
def revoke_access(*, grant_id, actor, correlation_id=""):
    grant = EmergencyAccessRequest.objects.select_for_update().select_related("patient", "clinician").get(pk=grant_id)
    if actor != grant.clinician and actor.role != User.Role.ADMIN:
        raise PermissionError("Not permitted")
    if grant.state == EmergencyAccessRequest.State.ACTIVE:
        grant.state = EmergencyAccessRequest.State.REVOKED; grant.revoked_at = timezone.now(); grant.save(update_fields=["state", "revoked_at"])
        audit.append_audit_event(actor=actor, action="revoke", resource_type="EmergencyAccessRequest", resource_id=grant.pk, patient=grant.patient, correlation_id=correlation_id)
    return grant


@transaction.atomic
def expire_access(*, at=None):
    at = at or timezone.now()
    grants = list(EmergencyAccessRequest.objects.select_for_update().filter(state=EmergencyAccessRequest.State.ACTIVE, expires_at__lte=at).select_related("patient", "clinician"))
    for grant in grants:
        grant.state = EmergencyAccessRequest.State.EXPIRED; grant.save(update_fields=["state"])
        audit.append_audit_event(actor=grant.clinician, action="expire", resource_type="EmergencyAccessRequest", resource_id=grant.pk, patient=grant.patient)
    return len(grants)
