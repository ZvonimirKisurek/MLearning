"""Runs the real SQL against Postgres 16 + pgvector 0.8: migrations, Phase 1 dedup lookups, Phase 2 engine."""
import json
from datetime import date, datetime, timedelta, timezone

import numpy as np
import psycopg
import pytest

from app.config import Settings
from app.curriculum import generators, repository as crepo
from app.ingestion import repository as irepo
from app.ingestion.models import RawItem, SourceSpec
from tests.factories import daily_dict, unit_vec, weekly_dict

rng = np.random.default_rng(1)
pytestmark = pytest.mark.integration


def seed_articles(n=24, per_source=4):
    specs = [SourceSpec(slug=f"s{i}", name=f"Source {i}", category="engineering_blog", url=f"https://s{i}.test/feed") for i in range(n // per_source)]
    irepo.upsert_sources(specs)
    states = irepo.load_source_states()
    vecs = []
    for i in range(n):
        v = unit_vec(rng)
        vecs.append(v)
        item = RawItem(title=f"Article {i}", url=f"https://s.test/{i}", summary=f"About {i}",
                       published_at=datetime.now(timezone.utc) - timedelta(hours=i))
        irepo.insert_article(states[f"s{i % len(specs)}"].id, item, item.url, f"hash{i}", v.tolist(), None, None)
    return vecs


class FakeEmbedder:
    def embed(self, texts):
        return [unit_vec(rng).tolist() for _ in texts]


class FakeLLM:
    """Builds a valid output from the grounding ids it is given - stands in for Claude."""
    def generate(self, *, system, user, output_model, grounding):
        ids = sorted(grounding.article_ids, key=lambda x: int(x[1:]))
        if output_model.__name__ == "WeeklyThemeOutput":
            d = weekly_dict(ids, skills=("rag", "vector-db"))
        else:
            d = daily_dict(ids[0], skill="rag", evidence=ids[:2])
        return output_model.model_validate(d, context=grounding)


def test_migrations_applied(db):
    with psycopg.connect(db) as conn:
        tables = {r[0] for r in conn.execute("select tablename from pg_tables where schemaname='public'")}
        assert {"sources", "articles", "ingestion_runs", "skills", "skill_history", "weekly_themes", "daily_briefings", "daily_tasks"} <= tables
        assert conn.execute("select count(*) from skills").fetchone()[0] == 7
        assert conn.execute("select data_type from information_schema.columns where table_name='skills' and column_name='level'").fetchone()[0] == "real"
        assert conn.execute("select bool_and(relrowsecurity) from pg_class where relname in ('articles','daily_tasks','skills')").fetchone()[0]


def test_phase1_dedup_lookup_uses_cosine_similarity(db):
    vecs = seed_articles(4, per_source=2)
    near = (vecs[0] + 0.02 * unit_vec(rng)).tolist()
    hit = irepo.find_nearest(near, window_days=14)
    assert hit is not None and hit[1] > 0.99
    assert irepo.find_nearest(unit_vec(rng).tolist(), window_days=14)[1] < 0.5  # unrelated text
    assert irepo.existing_url_hashes(["hash0", "nope"]) == {"hash0"}
    assert irepo.find_nearest(near, window_days=0) is None  # outside window => not a duplicate


def test_insert_article_is_idempotent_on_url_hash(db):
    seed_articles(2, per_source=2)
    states = irepo.load_source_states()
    item = RawItem(title="again", url="https://s.test/0")
    assert irepo.insert_article(states["s0"].id, item, item.url, "hash0", unit_vec(rng).tolist(), None, None) is None


def test_weekly_then_daily_end_to_end(db):
    seed_articles()
    s = Settings(timezone="UTC", min_candidates=10, prompt_article_count=20)
    day = date(2026, 10, 28)  # Wednesday
    w = generators.generate_weekly_theme(week_start=date(2026, 10, 26), llm=FakeLLM(), embedder=FakeEmbedder(), settings=s)
    assert not w["cached"] and len(w["payload"]["key_articles"]) == 3
    assert w["payload"]["key_articles"][0]["url"].startswith("https://s.test/")  # ids resolved to real URLs by code
    assert generators.generate_weekly_theme(week_start=date(2026, 10, 26), llm=FakeLLM(), embedder=FakeEmbedder(), settings=s)["cached"]

    d = generators.generate_daily_briefing(day=day, llm=FakeLLM(), embedder=FakeEmbedder(), settings=s)
    assert not d["cached"] and d["payload"]["morning_reading"]["url"].startswith("https://s.test/")
    assert generators.generate_daily_briefing(day=day, llm=FakeLLM(), embedder=FakeEmbedder(), settings=s)["cached"]
    with psycopg.connect(db) as conn:
        assert conn.execute("select count(*) from daily_tasks").fetchone()[0] == 3
        assert conn.execute("select count(*) from skills where embedding is not null").fetchone()[0] == 7

    # next day must not reuse yesterday's reading
    used = crepo.used_reading_ids()
    d2 = generators.generate_daily_briefing(day=date(2026, 10, 29), llm=FakeLLM(), embedder=FakeEmbedder(), settings=s)
    assert d2["payload"]["morning_reading"]["article_uuid"] not in used


def test_daily_self_heals_missing_weekly_theme_and_dry_run_prints_prompt(db):
    seed_articles()
    s = Settings(timezone="UTC", min_candidates=10)
    r = generators.generate_weekly_theme(week_start=date(2026, 10, 26), dry_run=True, embedder=FakeEmbedder(), settings=s)
    assert "<articles count=" in r["user"] and "ISO" not in r["user"] and crepo.get_weekly_theme(date(2026, 10, 26)) is None
    d = generators.generate_daily_briefing(day=date(2026, 10, 27), llm=FakeLLM(), embedder=FakeEmbedder(), settings=s)
    assert crepo.get_weekly_theme(date(2026, 10, 26)) is not None and d["payload"]["hands_on_task"]["title"]


def test_not_enough_data(db):
    with pytest.raises(generators.NotEnoughData):
        generators.generate_weekly_theme(week_start=date(2026, 10, 26), llm=FakeLLM(), embedder=FakeEmbedder(), settings=Settings())
