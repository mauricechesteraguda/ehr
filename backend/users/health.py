"""type-10022026-Maurice: Redacted liveness/readiness boundaries for local operations."""

import os
import time
from pathlib import Path
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.http import JsonResponse
from .tracing import trace_function
from .logging import log_event


@trace_function
def live(request):
    """type-10022026-Maurice: Return process liveness without dependency details."""
    log_event("health.live.success", component="health", operation="live", outcome="success", boundary="http")
    return JsonResponse({"status": "ok"})


@trace_function
def ready(request):
    """type-10022026-Maurice: Verify database connectivity and unapplied migrations."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        executor = MigrationExecutor(connection)
        pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if pending:
            log_event("health.ready.failure", component="health", operation="ready", outcome="failure", boundary="database", error_code="migrations_pending", remediation_hint="apply_migrations")
            return JsonResponse({"status": "unready", "reason": "migrations_pending"}, status=503)
    except Exception as error:
        log_event("health.ready.failure", component="health", operation="ready", outcome="failure", boundary="database", exception=error, remediation_hint="check_database")
        return JsonResponse({"status": "unready", "reason": "database_unavailable"}, status=503)
    log_event("health.ready.success", component="health", operation="ready", outcome="success", boundary="database")
    return JsonResponse({"status": "ready"})


@trace_function
def beat(request):
    """type-10022026-Maurice: Report scheduler heartbeat without exposing filesystem data."""
    heartbeat = Path(os.environ.get("BEAT_HEARTBEAT_FILE", "/run/ehr/beat-heartbeat"))
    if not heartbeat.exists() or time.time() - heartbeat.stat().st_mtime > 60:
        log_event("health.beat.failure", component="health", operation="beat", outcome="failure", boundary="scheduler", error_code="heartbeat_missing", remediation_hint="check_scheduler")
        return JsonResponse({"status": "unready", "reason": "scheduler_unavailable"}, status=503)
    log_event("health.beat.success", component="health", operation="beat", outcome="success", boundary="scheduler")
    return JsonResponse({"status": "ready"})
