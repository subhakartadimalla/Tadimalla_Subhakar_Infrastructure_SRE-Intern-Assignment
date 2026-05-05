#!/usr/bin/env sh
set -eu

echo "Running migrations..."
alembic upgrade head

echo "Starting API..."
exec uvicorn main:app --host 0.0.0.0 --port 8000 --no-access-log --log-level warning

