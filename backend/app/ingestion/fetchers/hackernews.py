"""Hacker News via the Algolia search API (official, no key). API => robots.txt does not apply."""
import time
from datetime import datetime, timezone

from app.config import Settings
from app.ingestion.http import PoliteClient
from app.ingestion.models import FetchResult, RawItem, SourceSpec, SourceState

API = "https://hn.algolia.com/api/v1/search_by_date"


def parse_hits(payload: dict) -> list[RawItem]:
    items = []
    for hit in payload.get("hits", []):
        title = hit.get("title") or hit.get("story_title")
        if not title:
            continue
        hn_url = f"https://news.ycombinator.com/item?id={hit['objectID']}"
        items.append(RawItem(
            title=title,
            url=hit.get("url") or hn_url,  # Ask HN / text posts have no external url
            summary=f"HN discussion ({hit.get('num_comments') or 0} comments): {hn_url}",
            author=hit.get("author"),
            published_at=datetime.fromtimestamp(hit["created_at_i"], tz=timezone.utc),
            engagement=hit.get("points"),
            metadata={"hn_id": hit["objectID"], "hn_url": hn_url},
        ))
    return items


async def fetch(spec: SourceSpec, state: SourceState, client: PoliteClient, settings: Settings) -> FetchResult:
    cfg = spec.config
    since = int(time.time()) - cfg.get("lookback_hours", 48) * 3600
    params = {
        "query": cfg["query"],
        "tags": cfg.get("tags", "story"),
        "numericFilters": f"points>={cfg.get('min_points', 20)},created_at_i>{since}",
        "hitsPerPage": cfg.get("max_items", settings.default_max_items),
    }
    resp = await client.get(API, params=params, respect_robots=False)
    resp.raise_for_status()
    return FetchResult(items=parse_hits(resp.json()))
