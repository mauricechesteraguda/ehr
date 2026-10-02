"""Ticket12: deterministic, visibly simulated Direct-shaped delivery boundary."""
import hashlib
import re
from pathlib import Path
from datetime import timedelta

from cryptography.fernet import Fernet
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .audit import append_audit_event
from .ccda import _key
from .models import CcdaDocument, DirectDelivery, DirectDeliveryAttempt, DirectDeliveryOutbox
from .tracing import trace_function
from backend.celery_app import app

RECIPIENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+\-]{0,63}@[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?){1,5}$")
PURPOSE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 .,;:'()/_+\-]{9,239}$")
MAX_RETRIES = 3


class AdapterError(Exception):
    code = "adapter_error"
    transient = False


class AdapterTimeout(AdapterError):
    code = "adapter_timeout"
    transient = True


class AdapterUnavailable(AdapterError):
    code = "adapter_unavailable"
    transient = True


class AdapterPermanentFailure(AdapterError):
    code = "adapter_rejected"


class DirectDeliveryAdapter:
    """Interface deliberately limited to local demo behavior; never opens a network connection."""
    def validate_recipient(self, recipient): raise NotImplementedError
    def enqueue(self, recipient, artifact_checksum): raise NotImplementedError
    def deliver(self, recipient, artifact_bytes): raise NotImplementedError
    def status(self, receipt_code): raise NotImplementedError


class LocalDemoDirectAdapter(DirectDeliveryAdapter):
    """Deterministic fixture adapter. It is not SMTP, DirectTrust, or a network client."""
    def validate_recipient(self, recipient):
        return isinstance(recipient, str) and len(recipient) <= 255 and bool(RECIPIENT_RE.fullmatch(recipient))

    def enqueue(self, recipient, artifact_checksum):
        self.validate_or_raise(recipient)
        return {"receipt_code": "SIM-" + hashlib.sha256((recipient + artifact_checksum).encode()).hexdigest()[:16]}

    def deliver(self, recipient, artifact_bytes):
        self.validate_or_raise(recipient)
        fixture = recipient.split("@", 1)[0].lower()
        if fixture.startswith("timeout"):
            raise AdapterTimeout()
        if fixture.startswith("unavailable") or fixture.startswith("transient"):
            raise AdapterUnavailable()
        if fixture.startswith("permanent") or fixture.startswith("reject"):
            raise AdapterPermanentFailure()
        checksum = hashlib.sha256(artifact_bytes).hexdigest()
        return {"receipt_code": "SIM-" + checksum[:16], "receipt_checksum": checksum}

    def status(self, receipt_code):
        return {"receipt_code": receipt_code, "state": "simulated"}

    def validate_or_raise(self, recipient):
        if not self.validate_recipient(recipient):
            raise AdapterPermanentFailure()


adapter = LocalDemoDirectAdapter()


def _artifact_bytes(document):
    """Read, decrypt, and checksum-bind a C-CDA artifact without exposing its path or bytes."""
    if document.direction != "export" or not document.artifact_path:
        raise AdapterPermanentFailure()
    if document.expires_at and document.expires_at <= timezone.now():
        raise AdapterPermanentFailure()
    try:
        encrypted = Path(document.artifact_path).read_bytes()
        body = Fernet(__import__("base64").urlsafe_b64encode(_key())).decrypt(encrypted)
    except Exception as exc:
        raise AdapterPermanentFailure() from exc
    if hashlib.sha256(body).hexdigest() != document.sha256:
        raise AdapterPermanentFailure()
    return body


@transaction.atomic
@trace_function
def enqueue_delivery(*, owner, artifact, recipient, purpose, idempotency_key):
    """Atomically create delivery, audit evidence, and payload-free outbox intent."""
    if not adapter.validate_recipient(recipient):
        raise ValueError("recipient")
    if not isinstance(purpose, str) or not PURPOSE_RE.fullmatch(purpose):
        raise ValueError("purpose")
    if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 160:
        raise ValueError("idempotency")
    if artifact.direction != "export" or (artifact.expires_at and artifact.expires_at <= timezone.now()):
        raise ValueError("artifact")
    # Hash only: recipient is never persisted, returned, logged, or audited.
    digest = hashlib.sha256(recipient.encode()).hexdigest()
    secret = Fernet(__import__("base64").urlsafe_b64encode(_key()))
    delivery, created = DirectDelivery.objects.get_or_create(
        idempotency_key=idempotency_key,
        defaults={"owner": owner, "artifact": artifact, "recipient_hash": digest, "recipient_ciphertext": secret.encrypt(recipient.encode()), "purpose": purpose, "max_attempts": MAX_RETRIES},
    )
    if not created and (delivery.recipient_hash != digest or delivery.artifact_id != artifact.pk or delivery.purpose != purpose):
        raise ValueError("idempotency")
    if created:
        DirectDeliveryOutbox.objects.create(delivery=delivery)
        append_audit_event(actor=owner, patient=artifact.patient, action="create", resource_type="DirectDelivery", resource_id=delivery.id)
    return delivery, created


def load_delivery_artifact(delivery):
    return _artifact_bytes(delivery.artifact)


def _recipient(delivery):
    try:
        return Fernet(__import__("base64").urlsafe_b64encode(_key())).decrypt(bytes(delivery.recipient_ciphertext)).decode()
    except Exception as exc:
        raise AdapterPermanentFailure() from exc


@app.task(bind=True, name="ehr.direct.deliver", ignore_result=True, acks_late=True)
@trace_function
def deliver_direct(self, delivery_id):
    """Deliver only through the local fixture and retain safe attempt/receipt metadata."""
    with transaction.atomic():
        delivery = DirectDelivery.objects.select_for_update().select_related("artifact", "owner").get(pk=delivery_id)
        now = timezone.now()
        if delivery.state in {DirectDelivery.State.SENT, DirectDelivery.State.CANCELLED, DirectDelivery.State.EXPIRED}:
            return
        if delivery.artifact.expires_at and delivery.artifact.expires_at <= now:
            delivery.state, delivery.finished_at, delivery.error_code = DirectDelivery.State.EXPIRED, now, "artifact_expired"
            delivery.save(update_fields=["state", "finished_at", "error_code", "updated_at"])
            return
        if delivery.attempts >= delivery.max_attempts:
            delivery.state, delivery.finished_at, delivery.error_code = DirectDelivery.State.FAILED, now, "retry_limit"
            delivery.save(update_fields=["state", "finished_at", "error_code", "updated_at"])
            return
        delivery.attempts += 1
        delivery.state = DirectDelivery.State.SENDING
        delivery.save(update_fields=["attempts", "state", "updated_at"])
        attempt = DirectDeliveryAttempt.objects.create(delivery=delivery, number=delivery.attempts, state=DirectDelivery.State.SENDING)
    try:
        recipient = _recipient(delivery)
        body = load_delivery_artifact(delivery)
        result = adapter.deliver(recipient, body)
    except AdapterError as exc:
        code, transient = exc.code, exc.transient
    except Exception:
        code, transient = "adapter_error", False
    else:
        with transaction.atomic():
            DirectDeliveryAttempt.objects.filter(pk=attempt.pk).update(state=DirectDelivery.State.SENT, outcome_code="delivered", receipt_checksum=result["receipt_checksum"], finished_at=timezone.now())
            DirectDelivery.objects.filter(pk=delivery.pk).update(state=DirectDelivery.State.SENT, finished_at=timezone.now(), receipt_code=result["receipt_code"], receipt_checksum=result["receipt_checksum"])
            DirectDeliveryOutbox.objects.filter(delivery=delivery, dispatched_at__isnull=True).update(dispatched_at=timezone.now())
            append_audit_event(actor=delivery.owner, patient=delivery.artifact.patient, action="update", resource_type="DirectDelivery", resource_id=delivery.id)
        return
    with transaction.atomic():
        DirectDeliveryAttempt.objects.filter(pk=attempt.pk).update(state=DirectDelivery.State.FAILED, outcome_code=code, finished_at=timezone.now())
        final = (not transient) or delivery.attempts >= delivery.max_attempts
        DirectDelivery.objects.filter(pk=delivery.pk).update(state=DirectDelivery.State.FAILED if final else DirectDelivery.State.QUEUED, finished_at=timezone.now() if final else None, error_code=code)
        append_audit_event(actor=delivery.owner, patient=delivery.artifact.patient, action="update", resource_type="DirectDelivery", resource_id=delivery.id)
