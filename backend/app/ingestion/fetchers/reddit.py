"""Reddit via the official OAuth API (app-only). reddit.com/robots.txt blocks generic crawlers, so we
neither scrape nor use the .rss endpoints; without credentials these sources are skipped."""
import time
from datetime import datetime, timezone

from app.config import Settings
from app.ingestion.http import PoliteClient
from app.ingestion.models import FetchResult, RawItem, SourceSkipped, SourceSpec, SourceState
from app.ingestion.parsers import clean_text

_token: tuple[str, float] | None = None  # (access_token, expires_at_monotonic)


async def _get_token(client: PoliteClient, settings: Settings) -> str:
    global _token
    if _token and _token[1] > time.monotonic() + 60:
        return _token[0]
    resp = await client.request(
        "POST", "https://www.reddit.com/api/v1/access_token",
        respect_robots=False,
        auth=(settings.reddit_client_id, settings.reddit_client_secret),
        data={"grant_type": "client_credentials"},
    )
    resp.raise_for_status()
    body = resp.json()
    _token = (body["access_token"], time.monotonic() + body.get("expires_in", 3600))
    return _token[0]


def parse_listing(payload: dict, min_score: int) -> list[RawItem]:
    items = []
    for child in payload.get("data", {}).get("children", []):
        d = child["data"]
        if d.get("stickied") or d.get("score", 0) < min_score:
            continue
        permalink = f"https://www.reddit.com{d['permalink']}"
        items.append(RawItem(
            title=d["title"],
            url=d["url"] if not d.get("is_self") else permalink,
            summary=clean_text(d.get("selftext")) or f"Reddit discussion: {permalink}",
            author=d.get("author"),
            published_at=datetime.fromtimestamp(d["created_utc"], tz=timezone.utc),
            engagement=d.get("score"),
            metadata={"reddit_url": permalink, "subreddit": d.get("subreddit")},
        ))
    return items


async def fetch(spec: SourceSpec, state: SourceState, client: PoliteClient, settings: Settings) -> FetchResult:
    if not (settings.reddit_client_id and settings.reddit_client_secret):
        raise SourceSkipped("REDDIT_CLIENT_ID/SECRET not set")
    token = await _get_token(client, settings)
    resp = await client.get(
        f"https://oauth.reddit.com/r/{spec.config['subreddit']}/top",
        params={"t": spec.config.get("window", "day"), "limit": spec.config.get("max_items", 25)},
        headers={"Authorization": f"Bearer {token}"},
        respect_robots=False,
    )
    resp.raise_for_status()
    return FetchResult(items=parse_listing(resp.json(), spec.config.get("min_score", 10)))
