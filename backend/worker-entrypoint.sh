#!/bin/sh
# type-10022026-Maurice: Worker heartbeat and exec boundary for safe container shutdown.
set -eu
rm -f /run/ehr/worker-heartbeat
celery -A backend.celery_app worker --loglevel=INFO --hostname=worker@%h --concurrency=1 &
pid=$!
trap 'kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true' INT TERM EXIT
while kill -0 "$pid" 2>/dev/null; do
    touch /run/ehr/worker-heartbeat
    sleep 5
done
wait "$pid"
