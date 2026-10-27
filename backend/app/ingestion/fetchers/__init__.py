"""Fetchers: one async function per source `kind`, all with the same signature."""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.config import Settings
from app.ingestion.http import PoliteClient
from app.ingestion.models import FetchResult, SourceSpec, SourceState
from app.ingestion.fetchers import github_trending, hackernews, hf_papers, reddit, rss

Fetcher = Callable[[SourceSpec, SourceState, PoliteClient, Settings], Awaitable[FetchResult]]

FETCHERS: dict[str, Fetcher] = {
    "rss": rss.fetch,
    "hackernews": hackernews.fetch,
    "reddit": reddit.fetch,
    "github_trending": github_trending.fetch,
    "hf_daily_papers": hf_papers.fetch,
}
