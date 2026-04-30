#!/bin/sh
set -eu

PORT="${PORT:-8000}"
WORKERS="${WEB_CONCURRENCY:-2}"
TIMEOUT="${GUNICORN_TIMEOUT:-180}"

exec gunicorn \
  --workers "${WORKERS}" \
  --worker-class uvicorn.workers.UvicornWorker \
  --timeout "${TIMEOUT}" \
  --bind "0.0.0.0:${PORT}" \
  backend.main:app
