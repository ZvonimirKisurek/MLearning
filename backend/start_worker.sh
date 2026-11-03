#!/usr/bin/env bash
# Runs the Celery worker (executes tasks) AND Celery beat (the clock that enqueues them) together, for local use.
# Needs Redis (REDIS_URL in .env). Usage:  ./start_worker.sh            (foreground, Ctrl-C stops both)
#                                          nohup ./start_worker.sh > worker.log 2>&1 &     (background)
# Run exactly ONE copy: two beats would enqueue every scheduled job twice.
set -euo pipefail
cd "$(dirname "$0")"

# Use the project venv if it exists and is not already active.
if [[ -z "${VIRTUAL_ENV:-}" && -f .venv/bin/activate ]]; then source .venv/bin/activate; fi

mkdir -p .celery
# Beat remembers when each job last ran in this file; keep it out of the source tree's way (see .gitignore).
BEAT_DB=.celery/celerybeat-schedule

# Pool: Celery's default "prefork" pool crashes every task on Python 3.14 + Celery 5.6 / billiard 4.3 here
# ("ValueError: not enough values to unpack"), which would make the 06:30 job fail silently. "threads" works and keeps
# 2-way concurrency (our tasks are I/O-bound: HTTP + DB + OpenAI). Override with:  POOL=prefork ./start_worker.sh
POOL="${POOL:-threads}"

pids=()
cleanup() { trap - INT TERM EXIT; kill "${pids[@]}" 2>/dev/null || true; wait 2>/dev/null || true; }
trap cleanup INT TERM EXIT

celery -A app.celery_app worker --loglevel=INFO --pool="$POOL" --concurrency=2 & pids+=($!)
celery -A app.celery_app beat   --loglevel=INFO --schedule="$BEAT_DB" --pidfile= & pids+=($!)

# If either process dies, take the other down too so a half-working scheduler never goes unnoticed.
# (Polling instead of `wait -n`: macOS ships bash 3.2, which lacks it.)
while kill -0 "${pids[0]}" 2>/dev/null && kill -0 "${pids[1]}" 2>/dev/null; do sleep 2; done
echo "A Celery process exited; shutting the other one down." >&2
exit 1
