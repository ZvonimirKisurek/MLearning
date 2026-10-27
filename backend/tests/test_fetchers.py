import httpx

from app.config import Settings
from app.ingestion.fetchers import hackernews, hf_papers, reddit, rss
from app.ingestion.http import PoliteClient
from app.ingestion.models import SourceSkipped, SourceSpec, SourceState
import pytest

SETTINGS = Settings(reddit_client_id="", reddit_client_secret="")


def client_for(handler):
    return PoliteClient("MLE-Sprint/0.1", min_interval=0, transport=httpx.MockTransport(handler))


def spec(kind, **config):
    return SourceSpec(slug="t", name="t", category="community", kind=kind, url="https://t.test/feed", config=config)


async def test_rss_not_modified_short_circuits():
    def handler(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        assert req.headers["if-none-match"] == '"abc"'
        return httpx.Response(304)

    res = await rss.fetch(spec("rss"), SourceState(etag='"abc"'), client_for(handler), SETTINGS)
    assert res.not_modified and res.items == []


async def test_rss_unparseable_raises():
    def handler(req):
        return httpx.Response(404) if req.url.path == "/robots.txt" else httpx.Response(200, text="<html>not a feed")

    with pytest.raises(ValueError):
        await rss.fetch(spec("rss"), SourceState(), client_for(handler), SETTINGS)


def test_hackernews_parse_handles_text_posts():
    items = hackernews.parse_hits({"hits": [
        {"objectID": "1", "title": "Ask HN: RAG?", "url": None, "points": 90, "num_comments": 3, "created_at_i": 1_700_000_000, "author": "a"},
        {"objectID": "2", "title": None, "created_at_i": 1},
    ]})
    assert len(items) == 1 and items[0].url.endswith("item?id=1") and items[0].engagement == 90


def test_hf_papers_uses_arxiv_url():
    items = hf_papers.parse_daily_papers(
        [{"paper": {"id": "2501.00001", "title": "T", "summary": "S", "upvotes": 42, "publishedAt": "2025-01-06T00:00:00.000Z"}}], 10
    )
    assert items[0].url == "https://arxiv.org/abs/2501.00001" and items[0].engagement == 42


def test_reddit_listing_filters_stickies_and_low_score():
    payload = {"data": {"children": [
        {"data": {"title": "a", "url": "https://x.test", "permalink": "/r/x/1", "score": 50, "created_utc": 1_700_000_000, "is_self": False}},
        {"data": {"title": "b", "url": "u", "permalink": "/r/x/2", "score": 1, "created_utc": 1}},
        {"data": {"title": "c", "url": "u", "permalink": "/r/x/3", "score": 99, "created_utc": 1, "stickied": True}},
    ]}}
    assert [i.title for i in reddit.parse_listing(payload, 10)] == ["a"]


async def test_reddit_skipped_without_credentials():
    with pytest.raises(SourceSkipped):
        await reddit.fetch(spec("reddit", subreddit="x"), SourceState(), client_for(lambda r: httpx.Response(200)), SETTINGS)
