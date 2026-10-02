#!/bin/sh
# type-10022026-Maurice: Beat heartbeat sidecar loop keeps scheduler liveness observable.
set -eu
rm -f /run/ehr/beat-heartbeat
celery -A backend.celery_app beat --loglevel=INFO &
pid=$!
trap 'kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true' INT TERM EXIT
while kill -0 "$pid" 2>/dev/null; do
    touch /run/ehr/beat-heartbeat
    sleep 5
done
wait "$pid"
