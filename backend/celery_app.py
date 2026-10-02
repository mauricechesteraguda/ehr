"""type-10022026-Maurice: Minimal Celery plumbing for Ticket01 startup health."""

import os
from celery import Celery

app = Celery("ehr", broker=os.environ.get("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0"), backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/1"))
app.conf.update(task_always_eager=False, task_ignore_result=True, include=["backend.users.jobs"], beat_schedule={
    "dispatch-job-outbox": {"task": "ehr.jobs.dispatch_outbox", "schedule": 10.0},
    "retain-job-metadata": {"task": "ehr.jobs.retain", "schedule": 86400.0},
    "expire-break-glass": {"task": "ehr.jobs.expire_break_glass", "schedule": 10.0},
    "expire-population-exports": {"task": "ehr.jobs.expire_population_exports", "schedule": 60.0},
    "enqueue-due-population-schedules": {"task": "ehr.jobs.enqueue_due_population_schedules", "schedule": 60.0},
})
app.autodiscover_tasks(["backend.users"])
