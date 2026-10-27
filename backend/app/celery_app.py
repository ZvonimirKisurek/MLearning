from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()
app = Celery("mle_sprint", broker=settings.redis_url, backend=settings.redis_url, include=["app.tasks"])
app.conf.update(
    timezone="UTC",
    task_acks_late=True,  # re-deliver if a worker dies mid-run (ingestion is idempotent via url_hash)
    worker_prefetch_multiplier=1,
    task_time_limit=60 * 60,
    beat_schedule={
        "ingest-every-6h": {"task": "app.tasks.ingest_all", "schedule": crontab(minute=0, hour="*/6")},
        # Phase 2: weekly theme (Sun 22:00 UTC) and daily briefing (06:00 UTC) get registered here.
    },
)
