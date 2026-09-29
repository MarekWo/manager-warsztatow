#!/bin/sh
# Container entrypoint for the web and worker services: optionally run first-run tasks, then
# exec the command. SQLite needs no waiting; the database file lives on the /data volume.
set -eu

# Only one service (web) runs migrations, so web and worker never race on schema changes.
if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
    python manage.py migrate --noinput
    python manage.py createcachetable
    python manage.py ensure_admin
    python manage.py seed_defaults
    python manage.py ensure_schedules
fi

exec "$@"
