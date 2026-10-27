import logging

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
