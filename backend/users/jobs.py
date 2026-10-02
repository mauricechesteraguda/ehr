"""Ticket02 job/outbox contract: database is authoritative, Redis is delivery only."""
import hashlib
import json
import logging
import re
from datetime import timedelta

from celery.exceptions import Retry
from django.db import transaction
from django.db.models import Q
from django.conf import settings
from django.utils import timezone

from backend.celery_app import app
from .logging import log_event
from .models import Job, JobAttempt, OutboxEvent
from .audit import append_audit_event
from .tracing import trace_function
from .break_glass import expire_access

logger = logging.getLogger("ehr.jobs")


class TransientJobError(Exception):
    """A dependency failure safe to retry without exposing its message."""


class PermanentJobError(Exception):
    """A malformed or unsupported job which must not be retried."""


def _redact_input(value):
    """Keep only bounded, non-sensitive contract metadata in PostgreSQL and Redis."""
    if not isinstance(value, dict):
        return {}
    allowed = {"format", "demo", "version", "requested_scope", "scope", "start_date", "end_date", "purpose", "cap", "schedule_id", "resource_types", "since", "approval"}
    result = {}
    source = value
    for key in sorted(source):
        if key not in allowed: continue
        item = source[key]
        result[key] = [str(child)[:40] for child in item[:20]] if key == "resource_types" and isinstance(item, list) else str(item)[:80]
    return result


@transaction.atomic
@trace_function
def enqueue_job(*, owner, kind, idempotency_key, patient=None, input_data=None, expires_at=None):
    """Atomically persist job plus audit/outbox intent; no broker call occurs in this transaction."""
    redacted = _redact_input(input_data or {})
    checksum = hashlib.sha256(json.dumps(redacted, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    job, created = Job.objects.get_or_create(
        owner=owner, idempotency_key=idempotency_key,
        defaults={"kind": kind, "patient": patient, "input_checksum": checksum, "redacted_input": redacted, "expires_at": expires_at},
    )
    if not created and (job.kind != kind or job.input_checksum != checksum):
        raise ValueError("idempotency key is already used")
    if created:
        OutboxEvent.objects.create(job=job, kind=kind)
        append_audit_event(actor=owner, patient=patient, action="create", resource_type="job", resource_id=job.id)
        log_event("job.queued", component="jobs", operation="enqueue", outcome="success")
    return job, created


@trace_function
def dispatch_pending(*, limit=50):
    """Claim with PostgreSQL row locks, publish opaque IDs, then mark dispatched."""
    dispatched = 0
    while dispatched < limit:
        with transaction.atomic():
            event = (OutboxEvent.objects.select_for_update(skip_locked=True)
                     .filter(state=OutboxEvent.State.PENDING)
                     .filter(Q(claimed_at__isnull=True) | Q(claimed_at__lt=timezone.now() - timedelta(minutes=5)))
                     .order_by("created_at").first())
            if event is None:
                break
            event.attempts += 1
            event.claimed_at = timezone.now()
            event.save(update_fields=["attempts", "claimed_at"])
            event_id, job_id = str(event.id), str(event.job_id)
        try:
            # type-10022026-Maurice: Redis receives opaque identifiers only.
            deliver_job.delay(job_id, event_id)
        except Exception as error:
            OutboxEvent.objects.filter(pk=event_id, state=OutboxEvent.State.PENDING).update(claimed_at=None)
            log_event("job.dispatch.failure", component="jobs", operation="dispatch", outcome="failure", exception=error)
            # Stop this drain cycle so a broker outage cannot hot-loop one event
            # until the bounded database attempt counter overflows.
            break
        with transaction.atomic():
            updated = OutboxEvent.objects.filter(pk=event_id, state=OutboxEvent.State.PENDING).update(state=OutboxEvent.State.DISPATCHED, dispatched_at=timezone.now(), claimed_at=None)
        if updated:
            dispatched += 1
            log_event("job.dispatched", component="jobs", operation="dispatch", outcome="success")
    return dispatched


@trace_function
def dispatch_status(*, limit=50):
    """type-10022026-Maurice: Expose broker dependency state without losing DB outbox intent."""
    try:
        count = dispatch_pending(limit=limit)
        return {"state": "available", "dispatched": count}
    except Exception as error:
        log_event("job.dispatch.dependency", component="jobs", operation="dispatch", outcome="deferred", exception=error)
        return {"state": "unavailable", "dispatched": 0, "error_code": "broker_unavailable"}


def _safe_error(error):
    code = getattr(error, "code", "")
    return type(error).__name__, code if isinstance(code, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,40}", code) else "job_error"


def _run_demo(job):
    """Deterministic no-op handler proving delivery/idempotency without clinical effects."""
    if job.kind == "population.export":
        from .population_exports import run_population_export
        run_population_export(job)
        return
    if job.kind == "fhir.bulk.export":
        from .bulk_exports import run_bulk_export
        run_bulk_export(job)
        return
    if job.kind == "ccda.export":
        from .ccda import generate_ccda
        generate_ccda(patient=job.patient, job=job)
        return
    if job.kind == "ccda.import":
        from .ccda import parse_ccda, _key
        from cryptography.fernet import Fernet
        from pathlib import Path
        import base64
        if not job.result_ref:
            raise PermanentJobError("missing_input")
        raw = Fernet(base64.urlsafe_b64encode(_key())).decrypt(Path(job.result_ref).read_bytes())
        parse_ccda(raw, patient=job.patient, job=job)
        return
    if job.kind == "quality.measure":
        from .quality import run_measure
        run = job.measure_run
        run.status = "running"; run.save(update_fields=["status"])
        run_measure(run.id)
        run.status = "succeeded"; run.save(update_fields=["status"])
        return
    if job.kind not in {"demo.noop", "job.demo"}:
        raise PermanentJobError("unsupported kind")


@app.task(bind=True, name="ehr.jobs.deliver", ignore_result=True, acks_late=True)
def deliver_job(self, job_id, event_id):
    """Idempotent worker: a locked terminal job is acknowledged as duplicate delivery."""
    now = timezone.now()
    with transaction.atomic():
        job = Job.objects.select_for_update().get(pk=job_id)
        if job.expires_at and job.expires_at <= now:
            job.state, job.finished_at = Job.State.EXPIRED, now
            job.save(update_fields=["state", "finished_at"])
            return
        if job.state in {Job.State.SUCCEEDED, Job.State.CANCELLED, Job.State.EXPIRED}:
            return
        if job.state == Job.State.RUNNING and job.heartbeat_at and job.heartbeat_at > now - timedelta(minutes=10):
            return
        if job.attempts >= job.max_attempts:
            job.state = Job.State.FAILED
            job.finished_at = now
            job.error_class, job.error_code = "RetryLimitExceeded", "retry_limit"
            job.save(update_fields=["state", "finished_at", "error_class", "error_code"])
            return
        job.attempts += 1
        job.state, job.started_at, job.heartbeat_at = Job.State.RUNNING, now, now
        job.save(update_fields=["attempts", "state", "started_at", "heartbeat_at"])
        attempt = JobAttempt.objects.create(job=job, number=job.attempts, heartbeat_at=now)
    log_event("job.received", component="jobs", operation="worker", outcome="started")
    try:
        _run_demo(job)
    except TransientJobError as error:
        error_class, error_code = _safe_error(error)
        with transaction.atomic():
            attempt = JobAttempt.objects.select_for_update().get(pk=attempt.pk)
            attempt.state, attempt.finished_at, attempt.error_class, attempt.error_code = Job.State.FAILED, timezone.now(), error_class, error_code
            attempt.save(update_fields=["state", "finished_at", "error_class", "error_code"])
            Job.objects.filter(pk=job.pk).update(state=Job.State.QUEUED, heartbeat_at=None, error_class=error_class, error_code=error_code)
            append_audit_event(actor=job.owner, patient=job.patient, action="update", resource_type="job", resource_id=job.id)
        log_event("job.retry", component="jobs", operation="worker", outcome="retry", exception=error)
        raise self.retry(exc=Retry("transient"), countdown=min(300, 2 ** max(0, job.attempts - 1)))
    except Exception as error:
        error_class, error_code = _safe_error(error)
        with transaction.atomic():
            JobAttempt.objects.filter(pk=attempt.pk).update(state=Job.State.FAILED, finished_at=timezone.now(), error_class=error_class, error_code=error_code)
            Job.objects.filter(pk=job.pk).update(state=Job.State.FAILED, finished_at=timezone.now(), error_class=error_class, error_code=error_code)
            append_audit_event(actor=job.owner, patient=job.patient, action="update", resource_type="job", resource_id=job.id)
        log_event("job.failed", component="jobs", operation="worker", outcome="failure", exception=error)
        return
    with transaction.atomic():
        JobAttempt.objects.filter(pk=attempt.pk).update(state=Job.State.SUCCEEDED, finished_at=timezone.now(), heartbeat_at=timezone.now())
        Job.objects.filter(pk=job.pk, state=Job.State.RUNNING).update(state=Job.State.SUCCEEDED, finished_at=timezone.now(), heartbeat_at=timezone.now())
        append_audit_event(actor=job.owner, patient=job.patient, action="update", resource_type="job", resource_id=job.id)
    log_event("job.completed", component="jobs", operation="worker", outcome="success")


@trace_function
def cancel_job(job_id, *, actor=None):
    """Cancellation is an audited DB state transition and races safely with a worker lock."""
    with transaction.atomic():
        job = Job.objects.select_for_update().get(pk=job_id)
        if job.state in {Job.State.QUEUED, Job.State.RUNNING}:
            job.state, job.finished_at = Job.State.CANCELLED, timezone.now()
            job.save(update_fields=["state", "finished_at"])
            append_audit_event(actor=actor or job.owner, patient=job.patient, action="cancel", resource_type="job", resource_id=job.id)
        return job


@trace_function
def heartbeat(job_id, attempt_id):
    """Refresh visibility without storing payload or worker identity."""
    now = timezone.now()
    JobAttempt.objects.filter(pk=attempt_id, job_id=job_id, state=Job.State.RUNNING).update(heartbeat_at=now)
    Job.objects.filter(pk=job_id, state=Job.State.RUNNING).update(heartbeat_at=now)


@trace_function
def retain_jobs(*, older_than_days=30):
    """Scheduled retention removes only terminal metadata after the documented window."""
    cutoff = timezone.now() - timedelta(days=older_than_days)
    return Job.objects.filter(state__in=[Job.State.SUCCEEDED, Job.State.FAILED, Job.State.EXPIRED, Job.State.CANCELLED], finished_at__lt=cutoff).delete()[0]


@app.task(name="ehr.jobs.dispatch_outbox", ignore_result=True)
def dispatch_outbox_task():
    return dispatch_pending()


@app.task(name="ehr.jobs.retain", ignore_result=True)
def retain_jobs_task():
    return retain_jobs()


@app.task(name="ehr.jobs.expire_break_glass", ignore_result=True)
def expire_break_glass_task():
    """type-10022026-Maurice: Idempotent exact-boundary emergency expiry."""
    return expire_access()


@app.task(name="ehr.jobs.expire_population_exports", ignore_result=True)
def expire_population_exports_task():
    from .population_exports import expire_population_exports
    return expire_population_exports()

@app.task(name="ehr.jobs.expire_bulk_exports", ignore_result=True)
def expire_bulk_exports_task():
    from .bulk_exports import expire_bulk_exports
    return expire_bulk_exports()


@app.task(name="ehr.jobs.enqueue_due_population_schedules", ignore_result=True)
def enqueue_due_population_schedules_task():
    from .models import PopulationExportSchedule
    from .population_exports import TTL
    from django.utils import timezone as tz
    now = tz.now()
    total = 0
    for schedule in PopulationExportSchedule.objects.filter(active=True, next_run_at__lte=now).select_related("owner"):
        key = f"schedule:{schedule.id}:{schedule.next_run_at.isoformat()}"
        payload = {"scope": schedule.scope, "format": schedule.format, "start_date": schedule.start_date.isoformat(), "end_date": schedule.end_date.isoformat(), "purpose": schedule.purpose, "cap": settings.POPULATION_EXPORT_CAP, "schedule_id": str(schedule.id)}
        job, created = enqueue_job(owner=schedule.owner, kind="population.export", idempotency_key=key, input_data=payload, expires_at=now + TTL)
        if created:
            from .models import PopulationExportArtifact
            PopulationExportArtifact.objects.create(job=job, schedule=schedule, owner=schedule.owner, format=schedule.format, path="", sha256="", expires_at=job.expires_at)
        schedule.next_run_at = now + timedelta(days=1 if schedule.cadence == "daily" else 7)
        if schedule.cadence == "once": schedule.active = False
        schedule.save(update_fields=["next_run_at", "active"])
        total += 1
    return total
