"""Ticket10 authorized population exports; bounded, encrypted, and fail-closed."""
from .logging import traced_operation
import base64
import csv
import hashlib
import io
import json
import os
import secrets
from datetime import timedelta
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from . import audit
from .models import Job, Patient, PopulationExportArtifact, PopulationExportSchedule

TTL = timedelta(hours=24)
FORMATS = {"csv", "jsonl"}


def _key():
    raw = settings.POPULATION_EXPORT_KEY
    if not raw:
        raise RuntimeError("population export encryption is not configured")
    try:
        key = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except Exception as exc:
        raise RuntimeError("population export encryption is not configured") from exc
    if len(key) not in {16, 24, 32}:
        raise RuntimeError("population export encryption is not configured")
    return key


def _rows(start_date, end_date, cap):
    qs = Patient.objects.filter(birth_date__gte=start_date, birth_date__lte=end_date).order_by("pk")
    count = qs.count()
    if count > cap:
        raise ValueError("population export cap exceeded")
    return qs.iterator(chunk_size=100)


def _plain_rows(start_date, end_date, cap, export_format):
    rows = _rows(start_date, end_date, cap)
    if export_format == "jsonl":
        stream = io.StringIO()
        for patient in rows:
            stream.write(json.dumps({"patient_id": patient.public_id, "display_name": patient.display_name, "birth_date": patient.birth_date.isoformat()}, sort_keys=True, separators=(",", ":")) + "\n")
        return stream.getvalue().encode()
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["patient_id", "display_name", "birth_date"])
    for patient in rows:
        writer.writerow([patient.public_id, patient.display_name, patient.birth_date.isoformat()])
    return stream.getvalue().encode()


def _decrypt(path):
    payload = Path(path).read_bytes()
    return AESGCM(_key()).decrypt(payload[:12], payload[12:], None)


@traced_operation
def run_population_export(job):
    """Worker entrypoint. Only bounded DB pages and opaque filesystem references are used."""
    data = job.redacted_input
    start_date = __import__("datetime").date.fromisoformat(data["start_date"])
    end_date = __import__("datetime").date.fromisoformat(data["end_date"])
    plain = _plain_rows(start_date, end_date, int(data["cap"]), data["format"])
    if len(plain) > settings.POPULATION_EXPORT_MAX_BYTES:
        raise ValueError("population export hard cap exceeded")
    encrypted = AESGCM(_key()).encrypt((nonce := secrets.token_bytes(12)), plain, None)
    root = Path(settings.POPULATION_EXPORT_ROOT).resolve(); root.mkdir(mode=0o700, parents=True, exist_ok=True)
    final = root / f"{secrets.token_urlsafe(32)}.bin"
    temp = root / f".{secrets.token_urlsafe(32)}.tmp"
    try:
        temp.write_bytes(nonce + encrypted); os.chmod(temp, 0o600); os.replace(temp, final)
        with transaction.atomic():
            artifact, _ = PopulationExportArtifact.objects.get_or_create(job=job, defaults={"schedule_id": data.get("schedule_id") or None, "owner": job.owner, "format": data["format"], "path": str(final), "sha256": hashlib.sha256(plain).hexdigest(), "size_bytes": len(plain), "expires_at": timezone.now() + TTL})
            if artifact.path != str(final):
                artifact.schedule_id = data.get("schedule_id") or None; artifact.format = data["format"]; artifact.path = str(final); artifact.sha256 = hashlib.sha256(plain).hexdigest(); artifact.size_bytes = len(plain); artifact.expires_at = timezone.now() + TTL
                artifact.save(update_fields=["schedule", "format", "path", "sha256", "size_bytes", "expires_at"])
            audit.append_audit_event(actor=job.owner, action="export", resource_type="PopulationExport", resource_id=artifact.id, correlation_id="")
        return artifact
    except Exception:
        temp.unlink(missing_ok=True); final.unlink(missing_ok=True)
        raise


@traced_operation
def expire_population_exports():
    now = timezone.now()
    for artifact in PopulationExportArtifact.objects.filter(expires_at__lte=now):
        try:
            Path(artifact.path).unlink(missing_ok=True)
            audit.append_audit_event(actor=artifact.owner, action="expire", resource_type="PopulationExport", resource_id=artifact.id)
            artifact.delete()
        except Exception:
            # Keep metadata when audit/storage cleanup cannot be proven complete.
            continue


@traced_operation
def download_bytes(artifact):
    if artifact.expires_at <= timezone.now() or not Path(artifact.path).is_file():
        raise FileNotFoundError
    return _decrypt(artifact.path)
