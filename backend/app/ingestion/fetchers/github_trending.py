"""GitHub Trending has no API, so this scrapes HTML (robots.txt is checked by the client)."""
from app.config import Settings
from app.ingestion.http import PoliteClient
from app.ingestion.models import FetchResult, SourceSpec, SourceState
from app.ingestion.parsers import parse_github_trending


async def fetch(spec: SourceSpec, state: SourceState, client: PoliteClient, settings: Settings) -> FetchResult:
    resp = await client.get(spec.url)
    resp.raise_for_status()
    items = parse_github_trending(resp.text, spec.config.get("max_items", settings.default_max_items))
    if not items:
        raise ValueError("no repos parsed - GitHub markup probably changed")
    return FetchResult(items=items)
