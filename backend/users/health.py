"""type-10022026-Maurice: Redacted liveness/readiness boundaries for local operations."""

import logging
import os
import time
from pathlib import Path
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.http import JsonResponse
from .tracing import trace_function

logger = logging.getLogger("ehr")


@trace_function
def live(request):
    """type-10022026-Maurice: Return process liveness without dependency details."""
    logger.info("health.live.success")
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
            logger.warning("health.ready.failure", extra={"reason": "migrations_pending"})
            return JsonResponse({"status": "unready", "reason": "migrations_pending"}, status=503)
    except Exception as error:
        logger.warning("health.ready.failure", extra={"reason": type(error).__name__})
        return JsonResponse({"status": "unready", "reason": "database_unavailable"}, status=503)
    logger.info("health.ready.success")
    return JsonResponse({"status": "ready"})


@trace_function
def beat(request):
    """type-10022026-Maurice: Report scheduler heartbeat without exposing filesystem data."""
    heartbeat = Path(os.environ.get("BEAT_HEARTBEAT_FILE", "/run/ehr/beat-heartbeat"))
    if not heartbeat.exists() or time.time() - heartbeat.stat().st_mtime > 60:
        logger.warning("health.beat.failure", extra={"reason": "heartbeat_missing"})
        return JsonResponse({"status": "unready", "reason": "scheduler_unavailable"}, status=503)
    logger.info("health.beat.success")
    return JsonResponse({"status": "ready"})
