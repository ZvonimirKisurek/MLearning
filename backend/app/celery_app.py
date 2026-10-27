from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()
app = Celery("mle_sprint", broker=settings.redis_url, backend=settings.redis_url, include=["app.tasks"])
app.conf.update(
    timezone=settings.timezone,  # beat schedules below are interpreted in the learner's timezone
    task_acks_late=True,  # re-deliver if a worker dies mid-run (ingestion is idempotent via url_hash)
    worker_prefetch_multiplier=1,
    task_time_limit=60 * 60,
    beat_schedule={
        "ingest-every-6h": {"task": "app.tasks.ingest_all", "schedule": crontab(minute=0, hour="*/6")},
        # 20 minutes after each ingestion run, summarise whatever it brought in.
        "summarize-after-ingest": {"task": "app.tasks.summarize_recent_articles", "schedule": crontab(minute=20, hour="*/6")},
        "weekly-theme-sunday-night": {"task": "app.tasks.generate_weekly_theme", "schedule": crontab(minute=0, hour=22, day_of_week="sun")},
        # 06:30 so the 06:00 ingestion run (which feeds the candidate pool) has finished.
        "daily-briefing-morning": {"task": "app.tasks.generate_daily_briefing", "schedule": crontab(minute=30, hour=6)},
    },
)
