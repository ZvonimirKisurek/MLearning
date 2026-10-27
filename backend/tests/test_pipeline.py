from datetime import datetime, timedelta, timezone

from app.config import Settings
from app.ingestion.pipeline import breaker_open
from app.ingestion.models import SourceState

S = Settings()


def test_breaker_closed_below_threshold():
    assert not breaker_open(SourceState(consecutive_failures=S.breaker_failures - 1, last_fetched_at=datetime.now(timezone.utc)), S)


def test_breaker_open_then_half_open_after_cooldown():
    now = datetime.now(timezone.utc)
    st = SourceState(consecutive_failures=S.breaker_failures, last_fetched_at=now - timedelta(hours=1))
    assert breaker_open(st, S, now)
    st.last_fetched_at = now - timedelta(hours=S.breaker_cooldown_hours + 1)
    assert not breaker_open(st, S, now)
