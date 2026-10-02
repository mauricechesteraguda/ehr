#!/bin/sh
# type-10022026-Maurice: Migration and synthetic seed boundary; never prints credentials.
set -eu
printf '%s\n' '{"event":"startup.migration.begin"}'
python /app/backend/manage.py migrate --noinput
printf '%s\n' '{"event":"startup.migration.success"}'
python /app/backend/manage.py seed_demo --password "$DEMO_PASSWORD"
printf '%s\n' '{"event":"startup.seed.success","synthetic":true}'
exec gunicorn backend.config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 30 --access-logfile - --error-logfile -
