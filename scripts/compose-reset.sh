#!/bin/sh
# type-10022026-Maurice: Destructive local reset requires an explicit confirmation flag.
set -eu
if [ "${1:-}" != "--confirm" ]; then
    printf '%s\n' 'DRY RUN: would run docker compose down --volumes and remove disposable PostgreSQL/Redis state.'
    printf '%s\n' 'Re-run with --confirm to execute this destructive reset.'
    exit 0
fi
printf '%s\n' '{"event":"reset.begin","destructive":true,"scope":"compose-volumes"}'
exec docker compose down --volumes
