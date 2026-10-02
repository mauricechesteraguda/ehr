"""Ticket11 acceptance coverage; names are the canonical CSV automation refs."""
import base64
import copy
import hashlib
import json
from datetime import date
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from django.conf import settings

pytestmark = pytest.mark.django_db


def _user(name, role="clinician"):
    from backend.users.models import User

    return User.objects.create_user(username=name, password="ticket11-safe", role=role)


def _job(patient, owner, key):
    from backend.users.jobs import enqueue_job

    return enqueue_job(owner=owner, patient=patient, kind="ccda.import", idempotency_key=key,
                       input_data={"format": "ccda", "version": "1.0"})[0]


def _patient_with_six_sections():
    from backend.users.models import AllergyIntolerance, Condition, Device, MedicationOrder, MedicationOrderVersion, Observation, Patient

    owner = _user("ticket11-clinician")
    patient = Patient.objects.create(public_id="P11", display_name="Synthetic P11", birth_date=date(1980, 1, 1), sex="female")
    AllergyIntolerance.objects.create(patient=patient, code="ALG", label="Synthetic allergy", recorded_date=date(2026, 1, 1), reaction="rash")
    Condition.objects.create(patient=patient, code="CON", label="Synthetic problem", recorded_date=date(2026, 1, 2), status="active")
    Observation.objects.create(patient=patient, code="OBS", label="Synthetic observation", value="12", unit="mg", recorded_date=date(2026, 1, 3))
    Device.objects.create(patient=patient, code="DEV", label="Synthetic device", udi="")
    order = MedicationOrder.objects.create(patient=patient, prescriber=owner)
    version = MedicationOrderVersion.objects.create(order=order, version=1, medication_code="MED", medication_name="Synthetic medicine", dose=1, dose_unit="mg", route="oral", frequency="daily", start_date=date(2026, 1, 4), quantity=1, indication="demo", created_by=owner, status="active")
    order.active_version = version
    order.save(update_fields=["active_version"])
    return patient, owner


def _export_body(patient, owner, tmp_path):
    from backend.users.ccda import _crypt
    from backend.users.jobs import deliver_job, enqueue_job

    job, _ = enqueue_job(owner=owner, patient=patient, kind="ccda.export", idempotency_key="export-11",
                          input_data={"format": "ccda", "version": "1.0"})
    deliver_job.apply(args=(str(job.pk), str(job.outbox_events.first().pk))).get()
    job.refresh_from_db()
    assert job.state == job.State.SUCCEEDED
    document = job.ccda_document
    encrypted = Path(document.artifact_path).read_bytes()
    assert b"ClinicalDocument" not in encrypted and b"Synthetic" not in encrypted
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest()[:32])).decrypt(encrypted)


def test_TC_EXP_0111_roundtrip_all_sections(tmp_path, settings):
    from backend.users.ccda import parse_ccda
    from backend.users.models import CcdaDocument, ReconciliationCandidate
    from xml.etree import ElementTree as ET

    settings.CCDA_ROOT = str(tmp_path)
    patient, owner = _patient_with_six_sections()
    body = _export_body(patient, owner, tmp_path)
    root = ET.fromstring(body)
    assert {section.get("code") for section in root.findall("section")} == {"demographics", "allergies", "problems", "medications", "devices", "observations"}
    imported = _job(patient, owner, "import-11")
    encrypted_input = Path(tmp_path) / "input-11"
    encrypted_input.write_bytes(Fernet(base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest()[:32])).encrypt(body))
    imported.result_ref = str(encrypted_input)
    imported.save(update_fields=["result_ref"])
    from backend.users.jobs import deliver_job
    deliver_job.apply(args=(str(imported.pk), str(imported.outbox_events.first().pk))).get()
    imported.refresh_from_db()
    assert imported.state == imported.State.SUCCEEDED
    document = imported.ccda_document
    assert document.direction == "import"
    assert document.sha256 == hashlib.sha256(body).hexdigest()
    assert ReconciliationCandidate.objects.filter(document=document, state="pending").count() == 5
    assert CcdaDocument.objects.filter(patient=patient).count() == 2


def test_TC_EXP_0112_rejects_hostile_inputs(tmp_path):
    from backend.users.ccda import MAX_BYTES, parse_ccda
    from backend.users.models import CcdaDocument, ReconciliationCandidate
    from xml.etree import ElementTree as ET

    patient, owner = _patient_with_six_sections()
    body = _export_body(patient, owner, tmp_path)
    duplicate_root = ET.fromstring(body)
    duplicate_root.append(copy.deepcopy(duplicate_root.find("section")))
    duplicate_root.attrib.pop("checksum", None)
    duplicate_canonical = ET.tostring(duplicate_root, encoding="utf-8", xml_declaration=True)
    duplicate_root.set("checksum", hashlib.sha256(duplicate_canonical).hexdigest())
    duplicate_sections = ET.tostring(duplicate_root, encoding="utf-8", xml_declaration=True)
    cases = [
        body.replace(b'<section code="devices">', b'<section code="bogus">', 1),
        duplicate_sections,
        body.replace(b"</ClinicalDocument>", b"<!DOCTYPE x [<!ENTITY laugh \"x\">]></ClinicalDocument>"),
        body.replace(b"checksum=\"", b"checksum=\"bad", 1),
        body.replace(b"<entry resource=\"Device\">", b"<entry resource=\"Unknown\">", 1),
        body[: body.find(b'<section code="observations">')] + body[body.find(b'<section code="observations">') + len(b'<section code="observations">'):],
        body + b"x" * (MAX_BYTES + 1),
    ]
    for index, data in enumerate(cases):
        job = _job(patient, owner, f"hostile-11-{index}")
        with pytest.raises(ValueError):
            parse_ccda(data, patient=patient, job=job)
        assert not CcdaDocument.objects.filter(job=job).exists()
        assert not ReconciliationCandidate.objects.filter(document__job=job).exists()
    billion_laughs = b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol1 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">]><ClinicalDocument />'
    with pytest.raises(ValueError):
        parse_ccda(billion_laughs, patient=patient, job=_job(patient, owner, "hostile-11-xxe"))


def test_TC_EXP_0113_decisions_are_atomic(monkeypatch):
    from backend.users.ccda import decide_candidate
    from backend.users.models import AuditEvent, Condition, CcdaDocument, Job, OutboxEvent, ReconciliationCandidate

    patient, owner = _patient_with_six_sections()
    job = Job.objects.create(owner=owner, patient=patient, kind="ccda.import", idempotency_key="decision-11", input_checksum="x" * 64)
    document = CcdaDocument.objects.create(job=job, patient=patient, direction="import", template_id="urn:ehr:ccda:transition", template_version="1.0", provenance={"actor": str(owner.pk)}, sha256="x" * 64, artifact_path="", size_bytes=1)
    candidate = ReconciliationCandidate.objects.create(document=document, patient=patient, section="problems", resource_type="Condition", payload={"code": "NEW", "label": "New problem", "date": "2026-02-01"}, source_fingerprint="a" * 64)
    before = Condition.objects.count()
    decided = decide_candidate(candidate_id=candidate.pk, clinician=owner, decision="accepted")
    assert decided.state == "accepted" and Condition.objects.count() == before + 1
    assert AuditEvent.objects.filter(resource_type="ReconciliationCandidate", resource_id=str(candidate.pk)).exists()
    assert OutboxEvent.objects.filter(job=job, kind="reconciliation.decided").exists()
    with pytest.raises(ValueError, match="stale"):
        decide_candidate(candidate_id=candidate.pk, clinician=owner, decision="accepted")

    pending = ReconciliationCandidate.objects.create(document=document, patient=patient, section="problems", resource_type="Condition", payload={"code": "ROLLBACK", "label": "Rollback", "date": "2026-02-02"}, source_fingerprint="b" * 64)
    monkeypatch.setattr("backend.users.ccda.append_audit_event", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("audit unavailable")))
    with pytest.raises(RuntimeError):
        decide_candidate(candidate_id=pending.pk, clinician=owner, decision="accepted")
    pending.refresh_from_db()
    assert pending.state == "pending"
    assert not Condition.objects.filter(code="ROLLBACK").exists()
    assert not OutboxEvent.objects.filter(job=job, kind="reconciliation.decided").count() > 1
