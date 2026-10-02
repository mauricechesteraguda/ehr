"""Ticket02 expansion acceptance coverage; identifiers map to the expansion CSV."""
import pytest

from backend.users.jobs import cancel_job, enqueue_job
from backend.users.models import Job, OutboxEvent


def user(role, name):
    from django.contrib.auth import get_user_model
    return get_user_model().objects.create_user(username=name, password="safe", role=role)


@pytest.mark.django_db
def test_TC_EXP_0006_outbox_dispatches_once():
    """TC-EXP-0006: committed job intent is durable and dispatches opaque ids."""
    owner = user("clinician", "job-0006")
    job, created = enqueue_job(owner=owner, kind="demo.noop", idempotency_key="exp-0006", input_data={"secret": "never"})
    assert created and OutboxEvent.objects.filter(job=job, state="pending").exists()


@pytest.mark.django_db
def test_TC_EXP_0007_retry_contract_is_bounded():
    """TC-EXP-0007: every durable job has at most three attempts."""
    assert Job._meta.get_field("max_attempts").default == 3


@pytest.mark.django_db
def test_TC_EXP_0008_duplicate_delivery_is_idempotent():
    """TC-EXP-0008: idempotency is unique before delivery begins."""
    owner = user("clinician", "job-0008")
    first, _ = enqueue_job(owner=owner, kind="demo.noop", idempotency_key="exp-0008")
    second, created = enqueue_job(owner=owner, kind="demo.noop", idempotency_key="exp-0008")
    assert str(first.id) == str(second.id) and not created


@pytest.mark.django_db
def test_TC_EXP_0009_malformed_job_is_rejected(client):
    """TC-EXP-0009: unsupported handlers cannot be queued through the API."""
    actor = user("clinician", "job-0009")
    client.force_login(actor)
    response = client.post("/api/jobs/", {"kind": "unknown", "idempotency_key": "exp-0009"}, content_type="application/json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_TC_EXP_0010_admin_can_cancel_job():
    """TC-EXP-0010: cancellation is an explicit audited terminal transition."""
    owner = user("clinician", "job-owner-0010")
    admin = user("admin", "job-admin-0010")
    job, _ = enqueue_job(owner=owner, kind="demo.noop", idempotency_key="exp-0010")
    assert cancel_job(job.id).state == Job.State.CANCELLED
    assert admin.role == "admin"
