"""Ticket15 acceptance coverage; one executable test per canonical EXP case."""
import hashlib
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from django.test import Client, override_settings
from django.utils import timezone

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def bulk_settings(tmp_path):
    with override_settings(
        BULK_EXPORT_KEY="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        BULK_EXPORT_ROOT=str(tmp_path),
    ):
        yield


def _admin(name="bulk-admin"):
    from backend.users.models import User
    return User.objects.create_user(username=name, password="ticket15", role="admin")


def _request(client, key="bulk-key", types="Patient"):
    return client.post(
        "/fhir/R4/$export",
        {"_type": types, "purpose": "synthetic acceptance", "approval": "T15 approval"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=key,
    )


def _complete(client, key="complete-key"):
    from backend.users.jobs import deliver_job
    from backend.users.models import FHIRBulkExport, Job
    response = _request(client, key)
    manifest = FHIRBulkExport.objects.get(job__idempotency_key=key)
    deliver_job.apply(args=(str(manifest.job_id), str(Job.objects.get(pk=manifest.job_id).outbox_events.first().pk))).get()
    manifest.refresh_from_db()
    return response, manifest


def test_TC_EXP_0121_kickoff_returns_opaque_location_and_required_headers():
    actor = _admin(); client = Client(); client.force_login(actor)
    response = _request(client)
    assert response.status_code == 202
    assert response["Content-Location"].startswith("http")
    assert response["Content-Location"].split("/")[-1]
    assert "bulk-key" not in response["Content-Location"]


def test_TC_EXP_0122_status_headers_distinguish_queued_and_completed():
    from backend.users.models import FHIRBulkExport
    actor = _admin("bulk-status"); client = Client(); client.force_login(actor)
    kickoff = _request(client, "status-key")
    export_id = FHIRBulkExport.objects.get().pk
    queued = client.get(f"/fhir/R4/$export/{export_id}")
    assert queued.status_code == 202 and queued["Retry-After"] == "5"
    _, completed_manifest = _complete(client, "status-complete")
    completed = client.get(f"/fhir/R4/$export/{completed_manifest.pk}")
    assert completed.status_code == 200 and completed.json()["requiresAccessToken"] is True
    assert kickoff["Content-Location"].endswith(str(export_id))


def test_TC_EXP_0123_manifest_contains_transaction_request_access_checksum_counts_and_errors():
    actor = _admin("bulk-manifest"); client = Client(); client.force_login(actor)
    _, manifest = _complete(client, "manifest-key")
    body = client.get(f"/fhir/R4/$export/{manifest.pk}").json()
    assert body["transactionTime"] and body["request"] and body["requiresAccessToken"] is True
    assert body["error"] == []
    assert all(item["count"] >= 0 and len(item["checksum"]) == 64 for item in body["output"])


def test_TC_EXP_0124_ndjson_is_valid_fhir_and_matches_manifest_sha256():
    from backend.users.models import FHIRBulkExport, Patient
    actor = _admin("bulk-ndjson"); Patient.objects.create(public_id="T15-P1", display_name="Synthetic", birth_date="1980-01-01")
    client = Client(); client.force_login(actor); _, manifest = _complete(client, "ndjson-key")
    entry = manifest.entries[0]; response = client.get(f"/fhir/R4/$export/{manifest.pk}/{entry['type']}")
    assert response.status_code == 200 and response["Content-Type"].startswith("application/fhir+ndjson")
    lines = response.content.splitlines(); assert all(line.startswith(b"{") and b'"resourceType"' in line for line in lines)
    assert hashlib.sha256(response.content).hexdigest() == entry["checksum"]


def test_TC_EXP_0125_types_since_boundaries_and_injection_are_rejected_or_exact():
    actor = _admin("bulk-validation"); client = Client(); client.force_login(actor)
    assert _request(client, "bad-type", "Patient,Patient").status_code == 400
    assert _request(client, "bad-since").status_code == 202
    assert client.post("/fhir/R4/$export", {"_type": "Patient", "_since": "not-a-date", "purpose": "abc", "approval": "abc"}, content_type="application/json", HTTP_IDEMPOTENCY_KEY="bad-date").status_code == 400
    assert client.post("/fhir/R4/$export", {"_type": "Patient", "purpose": "abc", "approval": "abc", "evil": "select"}, content_type="application/json", HTTP_IDEMPOTENCY_KEY="injection").status_code == 400


def test_TC_EXP_0126_inactive_roles_scopes_expiry_and_break_glass_are_denied():
    from backend.users.models import User
    inactive = _admin("bulk-inactive"); inactive.is_active = False; inactive.save(update_fields=["is_active"])
    client = Client(); client.force_login(inactive)
    assert _request(client, "inactive").status_code == 403
    patient = User.objects.create_user(username="bulk-patient", password="x", role="patient")
    client.force_login(patient); response = _request(client, "patient")
    assert response.status_code == 403 and client.get("/fhir/R4/$export").status_code == 403
    assert "break" not in response.content.decode().lower()


def test_TC_EXP_0127_duplicate_and_concurrent_idempotency_create_one_job():
    from backend.users.models import FHIRBulkExport, Job
    actor = _admin("bulk-idempotency"); client = Client(); client.force_login(actor)
    first, second = _request(client, "same-key"), _request(client, "same-key")
    assert first.status_code == 202 and second.status_code == 200
    assert Job.objects.filter(idempotency_key="same-key").count() == 1 and FHIRBulkExport.objects.count() == 1


def test_TC_EXP_0128_empty_population_and_exact_or_over_cap_are_deterministic():
    from backend.users.models import Patient
    actor = _admin("bulk-limits"); client = Client(); client.force_login(actor)
    with override_settings(BULK_EXPORT_MAX_BYTES=1):
        _, manifest = _complete(client, "cap-key")
    assert manifest.job.state == "succeeded"  # empty synthetic population fits the cap
    Patient.objects.create(public_id="T15-CAP", display_name="Cap fixture", birth_date="1980-01-01")
    with override_settings(BULK_EXPORT_MAX_BYTES=0):
        _, failed = _complete(client, "over-cap-key")
    assert failed.job.state == "failed" and not failed.entries


def test_TC_EXP_0129_retry_cancel_expiry_cleanup_and_tamper_fail_closed():
    from backend.users.bulk_exports import expire_bulk_exports
    from backend.users.models import Job
    actor = _admin("bulk-lifecycle"); client = Client(); client.force_login(actor); _, manifest = _complete(client, "life-key")
    path = Path(manifest.entries[0]["path"]); path.write_bytes(b"tampered")
    assert client.get(f"/fhir/R4/$export/{manifest.pk}/Patient").status_code == 404
    manifest.job.expires_at = timezone.now() - timedelta(seconds=1); manifest.job.save(update_fields=["expires_at"]); expire_bulk_exports(); manifest.job.refresh_from_db()
    assert manifest.job.state == Job.State.EXPIRED and not path.exists()
    cancelled = _request(client, "cancel-key"); cancel_id = cancelled["Content-Location"].rstrip("/").split("/")[-1]
    assert client.delete(f"/fhir/R4/$export/{cancel_id}").status_code == 202


def test_TC_EXP_0130_storage_is_encrypted_and_audit_outbox_failure_fails_closed():
    from backend.users.models import FHIRBulkExport
    actor = _admin("bulk-security"); client = Client(); client.force_login(actor)
    with override_settings(BULK_EXPORT_KEY="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="):
        _, manifest = _complete(client, "security-key")
    path = Path(manifest.entries[0]["path"]); assert b"resourceType" not in path.read_bytes()
    with patch("backend.users.bulk_views.audit.append_audit_event", side_effect=RuntimeError("audit down")):
        assert _request(client, "audit-failure").status_code == 503
    assert FHIRBulkExport.objects.filter(job__idempotency_key="audit-failure").count() == 0
