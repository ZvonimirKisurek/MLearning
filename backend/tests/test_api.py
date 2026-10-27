"""API integration tests: real FastAPI app (lifespan + async psycopg pool) over embedded Postgres+pgvector."""
import asyncio
from datetime import date, datetime, timezone

import httpx
import numpy as np
import psycopg
import pytest

from app.config import Settings, get_settings
from app.curriculum import generators, summaries
from app.curriculum.schemas import SummaryBatch
from app.ingestion import repository as irepo
from app.ingestion.models import RawItem
from app.main import create_app
from tests.factories import unit_vec
from tests.test_integration_db import FakeEmbedder, FakeLLM, seed_articles

pytestmark = pytest.mark.integration
rng = np.random.default_rng(7)
TODAY = datetime.now(timezone.utc).date()


@pytest.fixture
async def client(db, monkeypatch):
    monkeypatch.delenv("API_TOKEN", raising=False)
    get_settings.cache_clear()
    app = create_app()
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            c.app = app
            yield c
    get_settings.cache_clear()


def generate_today():
    s = Settings(timezone="UTC", min_candidates=10, prompt_article_count=20)
    generators.generate_daily_briefing(day=TODAY, llm=FakeLLM(), embedder=FakeEmbedder(), settings=s)


def task_ids(db):
    with psycopg.connect(db) as conn:
        return {k: str(i) for i, k in conn.execute("select id, kind from daily_tasks")}


# --------------------------------------------------------------------------------------------- today
async def test_today_pending_before_generation(client):
    r = await client.get("/api/today")
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "pending" and body["briefing"] is None and body["weekly_theme"] is None
    assert len(body["skills"]) == 7


async def test_today_ready_has_tasks_theme_and_resolved_urls(client, db):
    seed_articles()
    generate_today()
    body = (await client.get("/api/today")).json()
    assert body["state"] == "ready"
    assert [t["kind"] for t in body["briefing"]["tasks"]] == ["reading", "hands_on", "insight"]
    assert body["briefing"]["payload"]["morning_reading"]["url"].startswith("https://s.test/")
    assert body["weekly_theme"]["theme"]["title"] and len(body["weekly_theme"]["theme"]["daily_plan"]) == 7
    assert set(body) == {"date", "state", "briefing", "weekly_theme", "skills"}  # response_model fixes the contract
    assert set(body["briefing"]) == {"id", "day", "completed_at", "payload", "tasks"}


# --------------------------------------------------------------------------------------------- completion
async def test_complete_moves_skill_and_is_idempotent(client, db):
    seed_articles()
    generate_today()
    tid = task_ids(db)["hands_on"]
    r1 = (await client.post(f"/api/tasks/{tid}/complete")).json()
    assert not r1["already_completed"] and r1["skill"]["delta"] > 0 and r1["task"]["completed"]
    r2 = (await client.post(f"/api/tasks/{tid}/complete")).json()
    assert r2["already_completed"] and r2["skill"]["level"] == pytest.approx(r1["skill"]["level"], abs=1e-3)
    sk = {s["slug"]: s for s in (await client.get("/api/skills")).json()}[r1["skill"]["slug"]]
    assert sk["level"] == pytest.approx(r1["skill"]["level"], abs=0.01) and sk["delta_7d"] == pytest.approx(r1["skill"]["delta"], abs=1e-3)
    assert sk["percent_to_target"] == pytest.approx(sk["level"] / sk["target"] * 100, abs=0.1) and len(sk["history"]) == 1


async def test_commit_is_visible_to_other_connections_when_response_arrives(client, db):
    seed_articles()
    generate_today()
    tid = task_ids(db)["reading"]
    await client.post(f"/api/tasks/{tid}/complete")
    with psycopg.connect(db) as other:  # a different session: only committed data is visible
        assert other.execute("select completed_at is not null from daily_tasks where id=%s", (tid,)).fetchone()[0]


async def test_concurrent_double_click_awards_once(client, db):
    seed_articles()
    generate_today()
    tid = task_ids(db)["hands_on"]
    results = await asyncio.gather(*[client.post(f"/api/tasks/{tid}/complete") for _ in range(6)])
    assert all(r.status_code == 200 for r in results)
    assert sum(not r.json()["already_completed"] for r in results) == 1
    with psycopg.connect(db) as conn:
        assert conn.execute("select count(*) from skill_history").fetchone()[0] == 1


async def test_briefing_completes_when_all_three_done_and_errors(client, db):
    seed_articles()
    generate_today()
    ids = task_ids(db)
    flags = [(await client.post(f"/api/tasks/{ids[k]}/complete")).json()["briefing_completed"] for k in ("reading", "hands_on", "insight")]
    assert flags == [False, False, True]
    assert (await client.post("/api/tasks/00000000-0000-0000-0000-000000000000/complete")).status_code == 404
    assert (await client.post("/api/tasks/not-a-uuid/complete")).status_code == 422


# --------------------------------------------------------------------------------------------- feed
def with_skill_embeddings(db):
    from app.db import get_pool  # the app's pool sets search_path + registers the vector type

    with get_pool().connection() as conn:
        for r in conn.execute("select slug from skills").fetchall():
            conn.execute("update skills set embedding=%s where slug=%s", (unit_vec(rng), r["slug"]))


async def test_feed_keyset_pagination_walks_every_article_once(client, db):
    seed_articles(24)
    seen, cursor = [], None
    for _ in range(10):
        r = (await client.get("/api/feed", params={"limit": 5, **({"cursor": cursor} if cursor else {})})).json()
        seen += [i["id"] for i in r["items"]]
        cursor = r["next_cursor"]
        if not cursor:
            break
    assert len(seen) == 24 == len(set(seen))
    assert r["items"][-1]["skill_match"] is None  # no skill embeddings yet -> no match, still served


async def test_feed_hides_duplicates_and_reports_also_covered_by(client, db):
    vecs = seed_articles(4, per_source=2)
    states = irepo.load_source_states()
    with psycopg.connect(db) as conn:
        canon = str(conn.execute("select id from articles where url_hash='hash0'").fetchone()[0])
    dup = RawItem(title="Same story elsewhere", url="https://other.test/x", published_at=datetime.now(timezone.utc))
    irepo.insert_article(states["s1"].id, dup, dup.url, "dup1", vecs[0].tolist(), canon, 0.97)
    items = (await client.get("/api/feed")).json()["items"]
    assert len(items) == 4 and "Same story elsewhere" not in [i["title"] for i in items]
    assert next(i for i in items if i["id"] == canon)["also_covered_by"] == ["Source 1"]


async def test_feed_category_skill_and_relevance_sort(client, db):
    seed_articles(24)
    with_skill_embeddings(db)
    all_items = (await client.get("/api/feed", params={"limit": 50})).json()["items"]
    assert all(i["skill_match"] and i["skill_match"]["strength"] in ("strong", "moderate", "weak") for i in all_items)
    assert (await client.get("/api/feed", params={"category": "research"})).json()["items"] == []
    assert len((await client.get("/api/feed", params={"category": "engineering_blog", "limit": 50})).json()["items"]) == 24
    slug = all_items[0]["skill_match"]["skill_slug"]
    only = (await client.get("/api/feed", params={"skill": slug, "limit": 50})).json()["items"]
    assert only and all(i["skill_match"]["skill_slug"] == slug for i in only)
    rel = []
    cursor = None
    while True:
        r = (await client.get("/api/feed", params={"sort": "relevance", "limit": 7, **({"cursor": cursor} if cursor else {})})).json()
        rel += [i["relevance"] for i in r["items"]]
        cursor = r["next_cursor"]
        if not cursor:
            break
    assert len(rel) == 24 and rel == sorted(rel, reverse=True)


async def test_feed_validation(client):
    assert (await client.get("/api/feed", params={"limit": 500})).status_code == 422
    assert (await client.get("/api/feed", params={"category": "memes"})).status_code == 422
    assert (await client.get("/api/feed", params={"cursor": "garbage"})).status_code == 400
    ok = (await client.get("/api/feed", params={"sort": "relevance"}))
    assert ok.status_code == 200  # empty db is a valid, empty page
    assert ok.json() == {"items": [], "next_cursor": None}


# --------------------------------------------------------------------------------------------- ops / security
async def test_health_cors_and_auth(client, db, monkeypatch):
    assert (await client.get("/health")).json() == {"status": "ok"}
    pre = await client.options("/api/today", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"})
    assert pre.headers["access-control-allow-origin"] == "http://localhost:3000"
    bad = await client.options("/api/today", headers={"Origin": "https://evil.test", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in bad.headers

    monkeypatch.setenv("API_TOKEN", "s3cret")
    get_settings.cache_clear()
    assert (await client.get("/api/skills")).status_code == 401
    assert (await client.get("/api/skills", headers={"Authorization": "Bearer nope"})).status_code == 401
    assert (await client.get("/api/skills", headers={"Authorization": "Bearer s3cret"})).status_code == 200
    assert (await client.get("/health")).status_code == 200  # not behind the token


async def test_generate_endpoint_queues_only_when_needed(client, db):
    from app.api.deps import get_enqueue

    calls = []
    client.app.dependency_overrides[get_enqueue] = lambda: calls.append
    r = await client.post("/api/briefing/generate")
    assert r.status_code == 202 and r.json() == {"queued": True, "reason": None} and calls == ["app.tasks.generate_daily_briefing"]

    def broken(name):
        raise ConnectionError("redis down")
    client.app.dependency_overrides[get_enqueue] = lambda: broken
    assert (await client.post("/api/briefing/generate")).status_code == 503

    seed_articles()
    generate_today()
    client.app.dependency_overrides[get_enqueue] = lambda: calls.append
    assert (await client.post("/api/briefing/generate")).json()["reason"] == "already generated"
    assert len(calls) == 1


# --------------------------------------------------------------------------------------------- summaries
class FakeSummaryLLM:
    def generate(self, *, system, user, output_model, grounding, model=None, effort=None):
        assert output_model is SummaryBatch and model == "claude-haiku-5-5" and "untrusted" in system
        return output_model.model_validate({"summaries": [{"id": i, "summary": f"Summary for {i}."} for i in sorted(grounding.article_ids)]}, context=grounding)


async def test_summaries_fill_ai_summary_and_feed_serves_it(client, db):
    seed_articles(12)
    s = Settings(summary_batch_size=5)
    out = summaries.summarize_pending(llm=FakeSummaryLLM(), settings=s)
    assert out == {"summarized": 12, "failed": 0, "pending_seen": 12}
    assert summaries.summarize_pending(llm=FakeSummaryLLM(), settings=s)["pending_seen"] == 0  # idempotent
    items = (await client.get("/api/feed", params={"limit": 50})).json()["items"]
    assert all(i["ai_summary"] and i["ai_summary"].startswith("Summary for S") for i in items)


def test_summary_schema_requires_exact_coverage():
    from app.curriculum.schemas import GroundingContext
    ctx = GroundingContext(frozenset({"S1", "S2"}), frozenset())
    with pytest.raises(Exception, match="exactly one summary"):
        SummaryBatch.model_validate({"summaries": [{"id": "S1", "summary": "x"}]}, context=ctx)
    with pytest.raises(Exception, match="https"):
        SummaryBatch.model_validate({"summaries": [{"id": "S1", "summary": "see https://x.y"}, {"id": "S2", "summary": "y"}]}, context=ctx)
