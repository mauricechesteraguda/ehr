"""type-10022026-Maurice: Exact-byte, short-lived synthetic patient exports."""
import hashlib
import io
import json
import os
import secrets
import time
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from reportlab.pdfgen import canvas

from . import audit
from .logging import log_event
from .models import Patient, PatientExport
from .tracing import trace_function

TTL = timedelta(minutes=15)


@trace_function
def _record(patient):
    """type-10022026-Maurice: Build a bounded machine-readable synthetic record."""
    data = {"patient": {field: getattr(patient, field) for field in ("public_id", "display_name", "race", "ethnicity", "preferred_language", "sex", "sexual_orientation", "gender_identity", "birth_date", "death_date")}}
    data["patient"]["birth_date"] = data["patient"]["birth_date"].isoformat()
    data["patient"]["death_date"] = data["patient"]["death_date"].isoformat() if data["patient"]["death_date"] else None
    data["allergies"] = list(patient.allergyintolerance_records.values("code", "label", "reaction", "recorded_date"))
    data["conditions"] = list(patient.condition_records.values("code", "label", "status", "recorded_date"))
    data["observations"] = list(patient.observation_records.values("code", "label", "value", "unit", "recorded_date"))
    data["devices"] = list(patient.device_records.values("code", "label", "status", "recorded_date"))
    data["medications"] = list(patient.medication_orders.values("id", "prescriber_id", "active_version_id"))
    return data


@trace_function
def _dictionary():
    return {"patient.public_id": "Synthetic patient identifier", "patient.display_name": "Synthetic display name", "allergies": "Synthetic allergy records", "conditions": "Synthetic condition records", "observations": "Synthetic observations", "devices": "Synthetic read-only devices", "medications": "Synthetic medication order references"}


@trace_function
def _bytes(patient, export_format):
    """type-10022026-Maurice: Generate complete bytes in memory before any file is visible."""
    data = _record(patient)
    if export_format == PatientExport.Format.JSON:
        return json.dumps({"synthetic_demo": True, "record": data, "data_dictionary": _dictionary()}, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    output = io.BytesIO()
    pdf = canvas.Canvas(output)
    pdf.setTitle("Synthetic patient record - non-clinical demo")
    pdf.drawString(72, 760, "SYNTHETIC / NON-CLINICAL DEMONSTRATION")
    pdf.drawString(72, 742, "This document is not a clinical record and must not guide care.")
    y = 710
    for key, value in data["patient"].items():
        pdf.drawString(72, y, f"{key}: {value}"); y -= 16
    for section in ("allergies", "conditions", "observations", "devices", "medications"):
        pdf.drawString(72, y, f"{section}: {len(data[section])} synthetic item(s)"); y -= 16
    pdf.save()
    return output.getvalue()


@trace_function
def purge_expired():
    """type-10022026-Maurice: Remove expired database rows and files without logging identifiers."""
    now = timezone.now()
    started = time.monotonic()
    for artifact in PatientExport.objects.filter(expires_at__lte=now):
        try:
            Path(artifact.path).unlink(missing_ok=True)
            artifact.delete()
        except OSError as error:
            log_event("export.purge.failure", outcome="failure", status=500, http_status=500, duration_ms=int((time.monotonic()-started)*1000), component="export", operation="purge", exception=error)
    log_event("export.purge.success", outcome="success", status=200, http_status=200, duration_ms=int((time.monotonic()-started)*1000), component="export", operation="purge", db_outcome="success")


@trace_function
def create_export(*, patient, actor, export_format, correlation_id):
    """type-10022026-Maurice: Atomically publish one exact-byte artifact and its audit event."""
    started = time.monotonic()
    if export_format not in {PatientExport.Format.JSON, PatientExport.Format.PDF}:
        raise ValueError("Unsupported export format")
    purge_expired()
    expires = timezone.now() + TTL
    existing = PatientExport.objects.filter(patient=patient, requested_by=actor, format=export_format, expires_at__gt=timezone.now()).first()
    if existing and Path(existing.path).is_file():
        return existing
    if existing:
        existing.delete()
    payload = _bytes(patient, export_format)
    digest = hashlib.sha256(payload).hexdigest()
    root = Path(settings.EXPORT_ROOT).resolve(); root.mkdir(mode=0o700, parents=True, exist_ok=True)
    artifact_id = uuid4(); final_path = root / f"{secrets.token_urlsafe(24)}.{export_format}"
    temporary = root / f".{secrets.token_urlsafe(24)}.tmp"
    try:
        temporary.write_bytes(payload); os.chmod(temporary, 0o600); os.replace(temporary, final_path)
        with transaction.atomic():
            artifact = PatientExport.objects.create(artifact_id=artifact_id, patient=patient, requested_by=actor, format=export_format, path=str(final_path), sha256=digest, expires_at=expires)
            audit.append_audit_event(actor=actor, action="export", resource_type="PatientExport", resource_id=str(artifact_id), patient=patient, correlation_id=correlation_id)
        log_event("export.generation.success", outcome="success", component="export", operation="generate", duration_ms=int((time.monotonic() - started) * 1000), correlation_id=correlation_id)
        return artifact
    except Exception as error:
        temporary.unlink(missing_ok=True); final_path.unlink(missing_ok=True)
        log_event("export.generation.failure", outcome="failure", component="export", operation="generate", duration_ms=int((time.monotonic() - started) * 1000), correlation_id=correlation_id, exception=error)
        raise
