import logging

import anthropic
import psycopg

from app.celery_app import app

log = logging.getLogger(__name__)


@app.task(
    bind=True, name="app.tasks.ingest_all",
    autoretry_for=(psycopg.OperationalError,), retry_backoff=True, retry_backoff_max=600, max_retries=3,
)
def ingest_all(self) -> dict:
    from app.ingestion.pipeline import run_ingestion

    return run_ingestion(trigger="beat")

# Transient infrastructure errors are retried with exponential backoff. LLMValidationFailed / LLMRefusal /
# NotEnoughData are NOT retried here: repeating the identical request will not change the outcome.
_TRANSIENT = (anthropic.APIConnectionError, anthropic.RateLimitError, anthropic.InternalServerError, psycopg.OperationalError)


@app.task(bind=True, name="app.tasks.generate_weekly_theme", autoretry_for=_TRANSIENT, retry_backoff=True, retry_backoff_max=900, max_retries=4)
def generate_weekly_theme_task(self) -> dict:
    from app.curriculum.generators import generate_weekly_theme

    r = generate_weekly_theme()
    return {"week_start": r["week_start"], "title": r["payload"]["title"], "cached": r["cached"]}


@app.task(bind=True, name="app.tasks.generate_daily_briefing", autoretry_for=_TRANSIENT, retry_backoff=True, retry_backoff_max=900, max_retries=4)
def generate_daily_briefing_task(self) -> dict:
    from app.curriculum.generators import generate_daily_briefing

    r = generate_daily_briefing()
    return {"day": r["day"], "cached": r["cached"]}
