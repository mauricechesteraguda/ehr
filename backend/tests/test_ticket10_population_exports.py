"""Ticket10 population-export acceptance coverage."""
from datetime import date
import hashlib

import pytest
from django.utils import timezone

pytestmark = pytest.mark.django_db


def _user(role, username):
    from backend.users.models import User
    return User.objects.create_user(username=username, password="ticket10-test", role=role)


def _request(client, **overrides):
    payload = {
        "scope": "all-demo", "start_date": "1980-01-01", "end_date": "2026-12-31",
        "purpose": "synthetic validation", "format": "jsonl", "cap": 10, "cadence": "once",
    }
    payload.update(overrides)
    return client.post("/api/admin/population-exports/", payload, HTTP_IDEMPOTENCY_KEY=overrides.get("idempotency_key", "ticket10-export"))


def test_TC_EXP_0100_roles_and_fields(client):
    """Only administrators can queue the bounded all-demo export contract."""
    client.force_login(_user("clinician", "ticket10-clinician"))
    assert _request(client).status_code == 403
    client.force_login(_user("admin", "ticket10-admin"))
    response = _request(client)
    assert response.status_code == 202
    assert response.json()["format"] == "jsonl"
    assert "redacted_input" not in response.json()


def test_TC_EXP_0101_cap_and_empty(client, settings):
    from backend.users.models import Patient

    admin = _user("admin", "ticket10-cap")
    settings.POPULATION_EXPORT_CAP = 10
    for index in range(2):
        Patient.objects.create(public_id=f"T10{index}", display_name=f"Synthetic {index}", birth_date=date(2000, 1, index + 1))
    client.force_login(admin)
    assert _request(client, cap=1, idempotency_key="ticket10-cap-over").status_code == 202
    assert _request(client, cap=0, start_date="2030-01-01", end_date="2030-01-02", idempotency_key="ticket10-cap-empty").status_code == 202
    assert _request(client, cap=11, idempotency_key="ticket10-cap-invalid").status_code == 400


def test_TC_EXP_0102_worker_hash_encryption(tmp_path, settings):
    from backend.users.jobs import enqueue_job
    from backend.users.models import Patient
    from backend.users.population_exports import _decrypt, run_population_export

    settings.POPULATION_EXPORT_ROOT = str(tmp_path)
    settings.POPULATION_EXPORT_KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    Patient.objects.create(public_id="T102", display_name="Synthetic Worker", birth_date=date(2000, 1, 1))
    owner = _user("admin", "ticket10-worker")
    job, _ = enqueue_job(owner=owner, kind="population.export", idempotency_key="ticket10-worker", input_data={"format": "jsonl", "start_date": "1999-01-01", "end_date": "2001-01-01", "cap": 10})
    artifact = run_population_export(job)
    assert artifact.sha256 == hashlib.sha256(_decrypt(artifact.path)).hexdigest()
    assert _decrypt(artifact.path).startswith(b'{"birth_date":')
    assert b"Synthetic Worker" not in open(artifact.path, "rb").read()


def test_TC_EXP_0103_schedule_idempotency(client):
    client.force_login(_user("admin", "ticket10-schedule"))
    first = _request(client, cadence="daily", timezone="UTC", idempotency_key="ticket10-schedule")
    second = _request(client, cadence="daily", timezone="UTC", idempotency_key="ticket10-schedule")
    assert first.status_code == 202 and second.status_code == 200
    assert first.json()["job_id"] == second.json()["job_id"]


def test_TC_EXP_0104_lifecycle(client):
    from backend.users.models import Job

    client.force_login(_user("admin", "ticket10-lifecycle"))
    created = _request(client, idempotency_key="ticket10-lifecycle")
    artifact_id = created.json()["id"]
    assert client.post(f"/api/admin/population-exports/{artifact_id}/", {"action": "cancel"}).status_code == 200
    assert Job.objects.get(id=created.json()["job_id"]).state == Job.State.CANCELLED
    assert client.get(f"/api/admin/population-exports/{artifact_id}/download/").status_code == 404
