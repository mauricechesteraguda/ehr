"""Ticket11 bounded C-CDA transition package and clinician reconciliation service."""
import hashlib, json, os, re, time
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET
from cryptography.fernet import Fernet
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from defusedxml import ElementTree as SafeET
from .models import CcdaDocument, ReconciliationCandidate, Patient, AllergyIntolerance, Condition, Observation, Device, MedicationOrder
from .audit import append_audit_event
from .models import OutboxEvent

SECTIONS = ("demographics", "allergies", "problems", "medications", "devices", "observations")
TEMPLATE_ID, TEMPLATE_VERSION, MAX_BYTES = "urn:ehr:ccda:transition", "1.0", 10 * 1024 * 1024

def _key():
    return hashlib.sha256(settings.SECRET_KEY.encode()).digest()[:32]
def _crypt(data):
    return Fernet(__import__('base64').urlsafe_b64encode(_key())).encrypt(data)
def _safe_name(job_id): return hashlib.sha256(str(job_id).encode()).hexdigest()+".ccda"

def _entry(section, resource, obj):
    payload = {"id": str(obj.pk), "code": getattr(obj, "code", ""), "label": getattr(obj, "label", ""), "date": str(getattr(obj, "recorded_date", "") or "")}
    if section == "allergies": payload["reaction"] = getattr(obj, "reaction", "")
    if section == "problems": payload["status"] = getattr(obj, "status", "")
    if section == "observations": payload.update(value=getattr(obj, "value", ""), unit=getattr(obj, "unit", ""))
    e = ET.Element("entry", {"resource": resource}); e.text = json.dumps(payload, sort_keys=True, separators=(",", ":")); return e

def generate_ccda(*, patient, job):
    root = ET.Element("ClinicalDocument", {"templateId": TEMPLATE_ID, "version": TEMPLATE_VERSION, "patient": patient.public_id})
    sections = {s: ET.SubElement(root, "section", {"code": s}) for s in SECTIONS}
    ET.SubElement(sections["demographics"], "patient", {"publicId": patient.public_id, "birthDate": str(patient.birth_date), "sex": patient.sex})
    for o in patient.allergyintolerance_records.all(): sections["allergies"].append(_entry("allergies", "AllergyIntolerance", o))
    for o in patient.condition_records.all(): sections["problems"].append(_entry("problems", "Condition", o))
    for o in patient.medication_orders.select_related("active_version").all():
        if o.active_version: sections["medications"].append(_entry("medications", "MedicationRequest", o.active_version))
    for o in patient.device_records.all(): sections["devices"].append(_entry("devices", "Device", o))
    for o in patient.observation_records.all(): sections["observations"].append(_entry("observations", "Observation", o))
    body = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    checksum = hashlib.sha256(body).hexdigest(); root.set("checksum", checksum); body = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    path = Path(getattr(settings, "CCDA_ROOT", os.path.join(settings.BASE_DIR, "var", "ccda"))); path.mkdir(parents=True, exist_ok=True); artifact = path / _safe_name(job.id); artifact.write_bytes(_crypt(body))
    return CcdaDocument.objects.create(job=job, patient=patient, direction="export", template_id=TEMPLATE_ID, template_version=TEMPLATE_VERSION, provenance={"actor": str(job.owner_id), "job": str(job.id)}, sha256=hashlib.sha256(body).hexdigest(), size_bytes=len(body), artifact_path=str(artifact))

@transaction.atomic
def parse_ccda(data, *, patient, job):
    started = time.monotonic()
    if not isinstance(data, (bytes, bytearray)) or len(data) > MAX_BYTES: raise ValueError("oversize")
    if re.search(br"<!DOCTYPE|<!ENTITY|SYSTEM|PUBLIC", data, re.I): raise ValueError("unsafe_xml")
    try: root = SafeET.fromstring(data)
    except Exception: raise ValueError("invalid_xml")
    if root.tag != "ClinicalDocument" or root.get("templateId") != TEMPLATE_ID or root.get("version") != TEMPLATE_VERSION: raise ValueError("unsupported_template")
    supplied = root.get("checksum", ""); root.set("checksum", ""); canonical = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    if not supplied or supplied != hashlib.sha256(canonical).hexdigest(): raise ValueError("checksum")
    sections = root.findall("section")
    if len(sections) != len(SECTIONS) or {s.get("code") for s in sections} != set(SECTIONS): raise ValueError("sections")
    doc = CcdaDocument.objects.create(job=job, patient=patient, direction="import", template_id=TEMPLATE_ID, template_version=TEMPLATE_VERSION, provenance={"actor": str(job.owner_id), "job": str(job.id)}, sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data), artifact_path="")
    candidates=[]
    for sec in sections:
        for entry in sec.findall("entry"):
            resource=entry.get("resource"); payload=json.loads(entry.text or "{}")
            if resource not in {"AllergyIntolerance","Condition","MedicationRequest","Device","Observation"}: raise ValueError("unknown_resource")
            if not payload.get("code") or not payload.get("label"): raise ValueError("required_fields")
            if payload.get("date"):
                try: date.fromisoformat(payload["date"])
                except (TypeError, ValueError): raise ValueError("date")
            fp=hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
            candidates.append(ReconciliationCandidate(document=doc, patient=patient, section=sec.get("code"), resource_type=resource, payload=payload, source_fingerprint=fp))
    ReconciliationCandidate.objects.bulk_create(candidates)
    return doc, time.monotonic()-started

@transaction.atomic
def decide_candidate(*, candidate_id, clinician, decision):
    c=ReconciliationCandidate.objects.select_for_update().select_related("document","patient").get(pk=candidate_id)
    if c.state != c.State.PENDING: raise ValueError("stale")
    if decision not in {"accepted","rejected","deferred"}: raise ValueError("decision")
    if decision == "accepted":
        p=c.payload
        if c.resource_type == "Condition": Condition.objects.create(patient=c.patient, code=p.get("code", ""), label=p.get("label", ""), recorded_date=date.fromisoformat(p["date"]) if p.get("date") else None)
        elif c.resource_type == "AllergyIntolerance": AllergyIntolerance.objects.create(patient=c.patient, code=p.get("code", ""), label=p.get("label", ""), reaction=p.get("reaction", ""), recorded_date=date.fromisoformat(p["date"]) if p.get("date") else None)
        elif c.resource_type == "Observation": Observation.objects.create(patient=c.patient, code=p.get("code", ""), label=p.get("label", ""), value=p.get("value", ""), unit=p.get("unit", ""), recorded_date=date.fromisoformat(p["date"]) if p.get("date") else None)
    c.state, c.decided_by, c.decided_at = decision, clinician, timezone.now(); c.save(update_fields=["state","decided_by","decided_at"])
    append_audit_event(actor=clinician, patient=c.patient, action="update", resource_type="ReconciliationCandidate", resource_id=c.pk)
    OutboxEvent.objects.create(job=c.document.job, kind="reconciliation.decided")
    return c
