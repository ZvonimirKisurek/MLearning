"""Orchestration: retrieve -> build prompt -> generate (validated) -> enrich with real URLs -> store.

    skills (+embeddings) ─┐
    last 7d articles ─────┼─► rank_articles (top 50) ─► prompt ─► Claude ─► validated JSON ─► + URLs ─► DB
    weekly theme/history ─┘

Both generators are idempotent per week/day (a re-run returns the stored row) so Celery retries and
accidental double-fires never create duplicates or burn tokens. `force=True` regenerates.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config import Settings, get_settings
from app.curriculum import prompts, repository
from app.curriculum.llm import StructuredLLM
from app.curriculum.ranking import rank_articles
from app.curriculum.schemas import DailyBriefingOutput, GroundingContext, WeeklyThemeOutput
from app.curriculum.types import RankedArticle, Skill

log = logging.getLogger(__name__)


class NotEnoughData(RuntimeError):
    pass


def local_now(settings: Settings) -> datetime:
    return datetime.now(ZoneInfo(settings.timezone))


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def upcoming_monday(d: date) -> date:
    """The week the Sunday-night run plans for. On a Monday it plans that same (current) week."""
    return d if d.weekday() == 0 else d + timedelta(days=7 - d.weekday())


def ensure_skill_embeddings(skills: list[Skill], embedder, repo=repository, settings: Settings | None = None) -> list[Skill]:
    """Embed skill descriptions once and cache them in the DB. They are the *query vectors* for retrieval.
    The embedder (and so an OpenAI key) is only needed the first time, when some skill has no stored vector."""
    missing = [s for s in skills if s.embedding is None]
    if missing:
        import numpy as np
        embedder = embedder or _default_embedder(settings or get_settings())
        vecs = embedder.embed([f"{s.name}: {s.description}" for s in missing])
        for s, v in zip(missing, vecs):
            repo.set_skill_embedding(s.slug, v)
            s.embedding = np.asarray(v, dtype=np.float32)
    return skills


def _select(skills, settings, repo, *, exclude=None, boost=None) -> list[RankedArticle]:
    cands = repo.fetch_candidates(settings.candidate_window_days)
    if len(cands) < settings.min_candidates:
        raise NotEnoughData(f"only {len(cands)} recent articles; run ingestion first (need {settings.min_candidates})")
    return rank_articles(cands, skills, top_n=settings.prompt_article_count, max_per_source=settings.max_per_source,
                         exclude_ids=exclude, skill_boost=boost)


def _grounding(articles: list[RankedArticle], skills: list[Skill]) -> GroundingContext:
    return GroundingContext(frozenset(a.short_id for a in articles), frozenset(s.slug for s in skills))


def _article_ref(a: RankedArticle) -> dict:
    c = a.candidate
    return {"article_uuid": c.id, "title": c.title, "url": c.url, "source": c.source_name, "category": c.category}


def generate_weekly_theme(
    *, week_start: date | None = None, force: bool = False, dry_run: bool = False,
    llm: StructuredLLM | None = None, embedder=None, repo=repository, settings: Settings | None = None,
) -> dict:
    settings = settings or get_settings()
    today = local_now(settings).date()
    week_start = week_start or upcoming_monday(today)
    existing = repo.get_weekly_theme(week_start)
    if existing and not force and not dry_run:
        return {"id": str(existing["id"]), "week_start": week_start.isoformat(), "payload": existing["payload"], "cached": True}

    skills = ensure_skill_embeddings(repo.load_skills(), embedder, repo, settings)
    articles = _select(skills, settings, repo)
    user = prompts.build_weekly_prompt(week_start, today, skills, articles, settings.candidate_window_days)
    if dry_run:
        return {"system": prompts.WEEKLY_SYSTEM, "user": user, "articles": len(articles)}

    out = (llm or StructuredLLM(settings)).generate(
        system=prompts.WEEKLY_SYSTEM, user=user, output_model=WeeklyThemeOutput, grounding=_grounding(articles, skills))
    by_id = {a.short_id: a for a in articles}
    payload = out.model_dump()
    payload["key_articles"] = [_article_ref(by_id[i]) for i in out.key_article_ids]  # ids -> real URLs, by code
    theme_id = repo.save_weekly_theme(week_start, payload, replace=force)
    log.info("weekly theme saved: %s", out.title)
    return {"id": theme_id, "week_start": week_start.isoformat(), "payload": payload, "cached": False}


def generate_daily_briefing(
    *, day: date | None = None, force: bool = False, dry_run: bool = False,
    llm: StructuredLLM | None = None, embedder=None, repo=repository, settings: Settings | None = None,
) -> dict:
    settings = settings or get_settings()
    day = day or local_now(settings).date()
    existing = repo.get_briefing(day)
    if existing and not force and not dry_run:
        return {"id": str(existing["id"]), "day": day.isoformat(), "payload": existing["payload"], "cached": True}

    week_start = monday_of(day)
    theme_row = repo.get_weekly_theme(week_start)
    if theme_row is None:  # Sunday job missed or first run mid-week: self-heal rather than fail
        log.warning("no weekly theme for %s; generating on demand", week_start)
        generate_weekly_theme(week_start=week_start, llm=llm, embedder=embedder, repo=repo, settings=settings, dry_run=dry_run)
        theme_row = repo.get_weekly_theme(week_start)
        if theme_row is None and dry_run:
            raise NotEnoughData("dry run needs a stored weekly theme; run generate-weekly first")
    theme = theme_row["payload"]
    plan_entry = next(d for d in theme["daily_plan"] if d["day"] == day.isoweekday())

    skills = ensure_skill_embeddings(repo.load_skills(), embedder, repo, settings)
    articles = _select(skills, settings, repo, exclude=repo.used_reading_ids(),
                       boost={plan_entry["skill_slug"]: 1.3})  # bias retrieval toward today's skill
    user = prompts.build_daily_prompt(day, theme, plan_entry, skills, articles, repo.recent_work(day), settings.candidate_window_days)
    if dry_run:
        return {"system": prompts.DAILY_SYSTEM, "user": user, "articles": len(articles)}

    out = (llm or StructuredLLM(settings)).generate(
        system=prompts.DAILY_SYSTEM, user=user, output_model=DailyBriefingOutput, grounding=_grounding(articles, skills))
    by_id = {a.short_id: a for a in articles}
    payload = out.model_dump()
    payload["morning_reading"].update(_article_ref(by_id[out.morning_reading.article_id]))
    payload["market_insight"]["evidence"] = [_article_ref(by_id[i]) for i in out.market_insight.evidence_article_ids]
    tasks = [
        {"kind": "reading", "skill_slug": out.morning_reading.skill_slug, "difficulty": out.morning_reading.difficulty,
         "title": by_id[out.morning_reading.article_id].candidate.title},
        {"kind": "hands_on", "skill_slug": out.hands_on_task.skill_slug, "difficulty": out.hands_on_task.difficulty,
         "title": out.hands_on_task.title},
        {"kind": "insight", "skill_slug": out.market_insight.skill_slug, "difficulty": 1, "title": out.market_insight.headline},
    ]
    briefing_id = repo.save_briefing(day, str(theme_row["id"]), payload, tasks, replace=force)
    log.info("daily briefing saved for %s", day)
    return {"id": briefing_id, "day": day.isoformat(), "payload": payload, "cached": False}


def _default_embedder(settings: Settings):
    from app.ingestion.embeddings import OpenAIEmbedder
    return OpenAIEmbedder(settings)
