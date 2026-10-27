import feedparser

from app.config import Settings
from app.ingestion.http import PoliteClient
from app.ingestion.models import FetchResult, SourceSpec, SourceState
from app.ingestion.parsers import parse_feed_entries


async def fetch(spec: SourceSpec, state: SourceState, client: PoliteClient, settings: Settings) -> FetchResult:
    headers = {}
    if state.etag:
        headers["If-None-Match"] = state.etag
    if state.last_modified:
        headers["If-Modified-Since"] = state.last_modified
    resp = await client.get(spec.url, headers=headers)
    if resp.status_code == 304:
        return FetchResult(not_modified=True, etag=state.etag, last_modified=state.last_modified)
    resp.raise_for_status()
    parsed = feedparser.parse(resp.content)
    if parsed.bozo and not parsed.entries:
        raise ValueError(f"unparseable feed: {parsed.bozo_exception!r}")
    items = parse_feed_entries(parsed, spec.config.get("max_items", settings.default_max_items))
    return FetchResult(items=items, etag=resp.headers.get("ETag"), last_modified=resp.headers.get("Last-Modified"))
