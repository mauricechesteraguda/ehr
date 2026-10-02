"""type-10022026-Maurice: Fail-closed append-only audit chain service."""
import hashlib
import json
from datetime import timezone

from django.db import connection, transaction
from django.utils import timezone as django_timezone

from .logging import log_event
from .models import AuditEvent
from .tracing import trace_function

GENESIS = "0" * 64
PROTECTED_ACTIONS = frozenset({"create", "read", "update", "delete", "cancel", "refill", "print", "export"})


@trace_function
def _canonical(*, sequence, actor_id, occurred_at, patient_id, action, resource_type, resource_id, correlation_id, previous_hash):
    """type-10022026-Maurice: Serialize fixed fields deterministically without payloads."""
    data = {"sequence": sequence, "actor_id": actor_id, "occurred_at": occurred_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"), "patient_id": patient_id, "action": action, "resource_type": resource_type, "resource_id": resource_id, "correlation_id": correlation_id, "previous_hash": previous_hash}
    return json.dumps(data, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode()


@trace_function
def append_audit_event(*, actor, action, resource_type, resource_id, patient=None, correlation_id=""):
    """type-10022026-Maurice: Append one evidence record atomically and fail closed."""
    try:
        with transaction.atomic():
            previous = AuditEvent.objects.select_for_update().order_by("-sequence").first()
            previous_hash = previous.current_hash if previous else GENESIS
            occurred_at = django_timezone.now()
            with connection.cursor() as cursor:
                cursor.execute("SELECT nextval(pg_get_serial_sequence(%s, %s))", [AuditEvent._meta.db_table, "sequence"])
                sequence = cursor.fetchone()[0]
            current_hash = hashlib.sha256(_canonical(sequence=sequence, actor_id=actor.pk if actor else None, occurred_at=occurred_at, patient_id=patient.pk if patient else None, action=action, resource_type=resource_type, resource_id=str(resource_id), correlation_id=correlation_id[:80], previous_hash=previous_hash)).hexdigest()
            event = AuditEvent.objects.create(sequence=sequence, actor=actor, occurred_at=occurred_at, patient=patient, action=action, resource_type=resource_type, resource_id=str(resource_id), correlation_id=correlation_id[:80], previous_hash=previous_hash, current_hash=current_hash)
            return event
    except Exception as error:
        log_event("audit.append.failure", outcome="failure", component="audit", operation="append", exception=error)
        raise


@trace_function
def audit_protected_operation(*, actor, action, resource_type, resource_id, patient=None, correlation_id=""):
    """type-10022026-Maurice: Generic fail-closed seam for future protected operations."""
    if action not in PROTECTED_ACTIONS:
        raise ValueError("Unsupported protected audit action")
    return append_audit_event(actor=actor, action=action, resource_type=resource_type, resource_id=resource_id, patient=patient, correlation_id=correlation_id)


@trace_function
def verify_chain():
    """type-10022026-Maurice: Recompute every link and report the first tamper safely."""
    previous = GENESIS
    for event in AuditEvent.objects.order_by("sequence").iterator():
        expected = hashlib.sha256(_canonical(sequence=event.sequence, actor_id=event.actor_id, occurred_at=event.occurred_at, patient_id=event.patient_id, action=event.action, resource_type=event.resource_type, resource_id=event.resource_id, correlation_id=event.correlation_id, previous_hash=previous)).hexdigest()
        if event.previous_hash != previous or event.current_hash != expected:
            return {"valid": False, "sequence": event.sequence}
        previous = event.current_hash
    return {"valid": True, "count": AuditEvent.objects.count()}
