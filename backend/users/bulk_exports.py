"""Ticket15 bounded FHIR Bulk Data-style export; no patient selection or break-glass."""
import base64, hashlib, json, os, secrets
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from . import audit
from .fhir import ALL_RESOURCES, RESOURCE_MODELS, _patient_queryset, _resource
from .models import FHIRBulkExport, Job, Patient, MedicationOrderVersion, FamilyHistoryVersion, Questionnaire, QuestionnaireResponseVersion

TTL = timedelta(hours=24)
MAX_BYTES = 100 * 1024 * 1024

def _key():
    raw = settings.BULK_EXPORT_KEY
    if not raw: raise RuntimeError("bulk export encryption is not configured")
    try: key = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except Exception as exc: raise RuntimeError("bulk export encryption is not configured") from exc
    if len(key) not in (16, 24, 32): raise RuntimeError("bulk export encryption is not configured")
    return key

def parse_since(value):
    if not value: return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None: raise ValueError
        return parsed
    except (TypeError, ValueError): raise ValueError("invalid _since")

def _query(resource_type, since):
    if resource_type == "Patient": qs = Patient.objects.all().order_by("pk")
    elif resource_type == "MedicationRequest": qs = MedicationOrderVersion.objects.filter(status__in=("active", "draft")).select_related("order__patient").order_by("pk")
    elif resource_type == "FamilyMemberHistory": qs = FamilyHistoryVersion.objects.filter(status="active").select_related("history__patient").order_by("pk")
    elif resource_type == "Questionnaire": qs = Questionnaire.objects.filter(active_version__isnull=False).order_by("pk")
    elif resource_type == "QuestionnaireResponse": qs = QuestionnaireResponseVersion.objects.select_related("response__patient", "questionnaire_version").order_by("pk")
    else: qs = RESOURCE_MODELS[resource_type].objects.all().order_by("pk")
    if since and hasattr(qs.model, "created_at"): qs = qs.filter(created_at__gte=since)
    return qs.iterator(chunk_size=100)

def run_bulk_export(job):
    data = job.redacted_input; types = data["resource_types"]; since = parse_since(data.get("since"))
    root = Path(settings.BULK_EXPORT_ROOT).resolve(); root.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory = root / secrets.token_urlsafe(24); directory.mkdir(mode=0o700)
    files, total = [], 0
    try:
        for resource_type in types:
            plain = bytearray()
            for item in _query(resource_type, since):
                resource = _resource(resource_type, item)
                plain.extend(json.dumps(resource, sort_keys=True, separators=(",", ":")).encode() + b"\n")
                if total + len(plain) > settings.BULK_EXPORT_MAX_BYTES: raise ValueError("bulk export cap exceeded")
            payload = bytes(plain); total += len(payload)
            nonce = secrets.token_bytes(12); encrypted = AESGCM(_key()).encrypt(nonce, payload, None)
            path = directory / (secrets.token_urlsafe(24) + ".bin"); temp = directory / ("." + secrets.token_urlsafe(24) + ".tmp")
            temp.write_bytes(nonce + encrypted); os.chmod(temp, 0o600); os.replace(temp, path)
            files.append({"type": resource_type, "path": str(path), "count": payload.count(b"\n"), "checksum": hashlib.sha256(payload).hexdigest(), "size": len(payload)})
        now = timezone.now()
        with transaction.atomic():
            manifest = FHIRBulkExport.objects.select_for_update().get(job=job)
            if manifest.entries: return
            manifest.entries = files; manifest.total_bytes = total; manifest.transaction_time = now; manifest.save(update_fields=["entries", "total_bytes", "transaction_time"])
            audit.append_audit_event(actor=job.owner, action="complete", resource_type="FHIRBulkExport", resource_id=str(manifest.id))
    except Exception:
        for item in files: Path(item["path"]).unlink(missing_ok=True)
        directory.rmdir() if directory.exists() and not any(directory.iterdir()) else None
        raise

def decrypt_entry(entry):
    raw = Path(entry["path"]).read_bytes(); return AESGCM(_key()).decrypt(raw[:12], raw[12:], None)

def expire_bulk_exports():
    for manifest in FHIRBulkExport.objects.select_related("job").filter(job__expires_at__lte=timezone.now()):
        for entry in manifest.entries: Path(entry.get("path", "")).unlink(missing_ok=True)
        manifest.job.state = Job.State.EXPIRED; manifest.job.save(update_fields=["state"])

def public_manifest(request, manifest):
    job = manifest.job
    if job.state in (Job.State.QUEUED, Job.State.RUNNING):
        return {"transactionTime": None, "request": manifest.request_url, "requiresAccessToken": True}
    if job.state != Job.State.SUCCEEDED or not manifest.entries:
        return {"transactionTime": None, "request": manifest.request_url, "requiresAccessToken": True, "error": [{"type": "OperationOutcome", "url": ""}]}
    return {"transactionTime": manifest.transaction_time.isoformat().replace("+00:00", "Z"), "request": manifest.request_url,
            "requiresAccessToken": True, "output": [{"type": e["type"], "url": request.build_absolute_uri(f"/fhir/R4/$export/{manifest.id}/{e['type']}"), "count": e["count"], "checksum": e["checksum"]} for e in manifest.entries], "error": manifest.errors}

def download_bulk_entry(manifest, resource_type):
    if manifest.job.state != Job.State.SUCCEEDED or manifest.job.expires_at <= timezone.now(): raise FileNotFoundError
    entry = next((e for e in manifest.entries if e["type"] == resource_type), None)
    if not entry: raise FileNotFoundError
    payload = decrypt_entry(entry)
    if hashlib.sha256(payload).hexdigest() != entry["checksum"]: raise FileNotFoundError
    return payload
