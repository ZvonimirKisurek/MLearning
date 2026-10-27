"""Hugging Face Daily Papers (community-curated trending arXiv papers) via its public JSON API."""
from datetime import datetime

from app.config import Settings
from app.ingestion.http import PoliteClient
from app.ingestion.models import FetchResult, RawItem, SourceSpec, SourceState
from app.ingestion.parsers import clean_text


def parse_daily_papers(payload: list[dict], max_items: int) -> list[RawItem]:
    items = []
    for row in payload[:max_items]:
        paper = row.get("paper") or {}
        if not paper.get("id") or not paper.get("title"):
            continue
        published = paper.get("publishedAt") or row.get("publishedAt")
        items.append(RawItem(
            title=clean_text(paper["title"], 300),
            # Use the arXiv abs URL so exact-URL dedup collapses this with the arXiv RSS sources.
            url=f"https://arxiv.org/abs/{paper['id']}",
            summary=clean_text(paper.get("summary")),
            published_at=datetime.fromisoformat(published.replace("Z", "+00:00")) if published else None,
            engagement=paper.get("upvotes"),
            metadata={"hf_url": f"https://huggingface.co/papers/{paper['id']}"},
        ))
    return items


async def fetch(spec: SourceSpec, state: SourceState, client: PoliteClient, settings: Settings) -> FetchResult:
    resp = await client.get(spec.url, respect_robots=False)
    resp.raise_for_status()
    return FetchResult(items=parse_daily_papers(resp.json(), spec.config.get("max_items", 50)))
