"""Ticket12 acceptance coverage; each function is referenced by the CSV evidence."""
import base64
import hashlib
import socket
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from django.conf import settings
from django.utils import timezone

pytestmark = pytest.mark.django_db


def _fixture(tmp_path, recipient="clinician@example.test"):
    from backend.users.models import CcdaDocument, Job, Patient, User

    suffix = uuid.uuid4().hex[:8]
    owner = User.objects.create_user(username=f"ticket12-clinician-{suffix}", password="safe", role="clinician")
    patient = Patient.objects.create(public_id=f"P12{suffix[:5]}", display_name="Synthetic P12", birth_date=date(1980, 1, 1))
    job = Job.objects.create(owner=owner, patient=patient, kind="ccda.export", idempotency_key=f"job-12-{suffix}", input_checksum="a" * 64)
    body = b'<ClinicalDocument><synthetic>true</synthetic></ClinicalDocument>'
    encrypted = Fernet(base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest()[:32])).encrypt(body)
    path = Path(tmp_path) / "artifact"
    path.write_bytes(encrypted)
    artifact = CcdaDocument.objects.create(job=job, patient=patient, direction="export", template_id="urn:ehr:ccda:transition", template_version="1.0", provenance={"actor": str(owner.pk)}, sha256=hashlib.sha256(body).hexdigest(), artifact_path=str(path), size_bytes=len(body), expires_at=timezone.now() + timedelta(hours=1))
    return owner, patient, artifact, body


def _delivery(tmp_path, monkeypatch, recipient="clinician@example.test"):
    from backend.users.direct_delivery import enqueue_delivery
    owner, patient, artifact, body = _fixture(tmp_path, recipient)
    delivery, created = enqueue_delivery(owner=owner, artifact=artifact, recipient=recipient, purpose="Continuity of care", idempotency_key=f"delivery-12-{recipient.split('@', 1)[0]}")
    assert created
    return owner, patient, artifact, body, delivery


def test_TC_EXP_0114_boundaries(tmp_path):
    from backend.users.direct_delivery import enqueue_delivery
    owner, patient, artifact, body = _fixture(tmp_path)
    for recipient, purpose in [("bad value", "Continuity of care"), ("x@example.test\nsecret", "Continuity of care"), ("clinician@example.test", "short"), ("clinician@example.test", "<script>alert(1)</script>")]:
        with pytest.raises(ValueError):
            enqueue_delivery(owner=owner, artifact=artifact, recipient=recipient, purpose=purpose, idempotency_key=recipient[:10] + purpose[:5])
    delivery, _ = enqueue_delivery(owner=owner, artifact=artifact, recipient="clinician@example.test", purpose="Continuity of care", idempotency_key="valid-12")
    assert delivery.recipient_hash == hashlib.sha256(b"clinician@example.test").hexdigest()


def test_TC_EXP_0115_roles_and_idempotency(tmp_path):
    from backend.users.models import AuditEvent, DirectDelivery, DirectDeliveryOutbox, User
    from backend.users.direct_delivery import enqueue_delivery
    owner, patient, artifact, body = _fixture(tmp_path)
    first, created = enqueue_delivery(owner=owner, artifact=artifact, recipient="clinician@example.test", purpose="Continuity of care", idempotency_key="same-12")
    same, duplicate = enqueue_delivery(owner=owner, artifact=artifact, recipient="clinician@example.test", purpose="Continuity of care", idempotency_key="same-12")
    assert created and not duplicate and first.pk == same.pk
    with pytest.raises(ValueError):
        enqueue_delivery(owner=owner, artifact=artifact, recipient="other@example.test", purpose="Continuity of care", idempotency_key="same-12")
    assert DirectDelivery.objects.count() == DirectDeliveryOutbox.objects.count() == 1
    assert AuditEvent.objects.filter(resource_type="DirectDelivery", action="create").count() == 1
    assert "clinician@example.test" not in str(first.__dict__)


def test_TC_EXP_0116_adapter_outcomes(tmp_path, monkeypatch):
    from backend.users.direct_delivery import deliver_direct
    from backend.users.models import DirectDelivery
    owner, patient, artifact, body, success = _delivery(tmp_path, monkeypatch)
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    deliver_direct.run(str(success.pk))
    success.refresh_from_db()
    assert success.state == DirectDelivery.State.SENT and success.receipt_code.startswith("SIM-")
    assert success.recipient_ciphertext and success.recipient_hash
    for local, expected in [("timeout@example.test", "adapter_timeout"), ("unavailable@example.test", "adapter_unavailable"), ("permanent@example.test", "adapter_rejected")]:
        _, _, _, _, item = _delivery(tmp_path, monkeypatch, local)
        for _ in range(3 if expected in {"adapter_timeout", "adapter_unavailable"} else 1):
            deliver_direct.run(str(item.pk)); item.refresh_from_db()
        assert item.error_code == expected
        assert item.attempts == (3 if expected in {"adapter_timeout", "adapter_unavailable"} else 1)


def test_TC_EXP_0117_retry_cancel(tmp_path):
    from backend.users.direct_delivery import deliver_direct
    from backend.users.models import DirectDelivery, DirectDeliveryAttempt
    _, _, _, _, item = _delivery(tmp_path, None, "transient@example.test")
    for _ in range(3):
        deliver_direct.run(str(item.pk))
        item.refresh_from_db()
    assert item.state == DirectDelivery.State.FAILED and item.attempts == 3
    assert DirectDeliveryAttempt.objects.filter(delivery=item).count() == 3
    _, _, _, _, cancelled = _delivery(tmp_path, None, "cancel@example.test")
    cancelled.state = DirectDelivery.State.CANCELLED; cancelled.save(update_fields=["state", "updated_at"])
    deliver_direct.run(str(cancelled.pk)); cancelled.refresh_from_db()
    assert cancelled.state == DirectDelivery.State.CANCELLED and cancelled.attempts == 0


def test_TC_EXP_0118_artifact_fail_closed(tmp_path):
    from backend.users.direct_delivery import deliver_direct
    from backend.users.models import DirectDelivery
    _, _, artifact, _, item = _delivery(tmp_path, None)
    type(artifact).objects.filter(pk=artifact.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
    deliver_direct.run(str(item.pk)); item.refresh_from_db()
    assert item.state == DirectDelivery.State.EXPIRED and item.attempts == 0
    _, _, artifact2, _, item2 = _delivery(tmp_path, None, "missing@example.test")
    Path(artifact2.artifact_path).unlink()
    deliver_direct.run(str(item2.pk)); item2.refresh_from_db()
    assert item2.state == DirectDelivery.State.FAILED and item2.error_code == "adapter_rejected"
    _, _, artifact3, body3, item3 = _delivery(tmp_path, None, "tampered@example.test")
    Path(artifact3.artifact_path).write_bytes(b"tampered")
    deliver_direct.run(str(item3.pk)); item3.refresh_from_db()
    assert item3.state == DirectDelivery.State.FAILED and item3.error_code == "adapter_rejected"
    assert item3.receipt_code == "" and item3.receipt_checksum == ""


def test_TC_EXP_0119_atomic_rollback(tmp_path, monkeypatch):
    from backend.users.direct_delivery import enqueue_delivery
    from backend.users.models import AuditEvent, DirectDelivery, DirectDeliveryOutbox
    owner, patient, artifact, body = _fixture(tmp_path)
    monkeypatch.setattr("backend.users.direct_delivery.append_audit_event", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("audit")))
    with pytest.raises(RuntimeError):
        enqueue_delivery(owner=owner, artifact=artifact, recipient="clinician@example.test", purpose="Continuity of care", idempotency_key="rollback-12")
    assert not DirectDelivery.objects.filter(idempotency_key="rollback-12").exists()
    assert not DirectDeliveryOutbox.objects.exists() and not AuditEvent.objects.exists()
    monkeypatch.undo()
    monkeypatch.setattr("backend.users.direct_delivery.DirectDeliveryOutbox.objects.create", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("outbox")))
    with pytest.raises(RuntimeError):
        enqueue_delivery(owner=owner, artifact=artifact, recipient="clinician@example.test", purpose="Continuity of care", idempotency_key="rollback-outbox-12")
    assert not DirectDelivery.objects.filter(idempotency_key="rollback-outbox-12").exists()
    assert not DirectDeliveryOutbox.objects.exists() and not AuditEvent.objects.exists()
