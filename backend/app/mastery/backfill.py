"""Bring lessons generated BEFORE the mastery loop (or simply not done yet) up to date, without deleting anything.

    python -m app.cli backfill-mastery [--days 14] [--no-llm] [--dry-run]

For every briefing in the last `days` days (today included):
  * review cards from the chapter's 'Check Your Understanding' questions, and teach-back cards from the week's core
    questions (no LLM; idempotent thanks to dedupe keys);
  * for an UNFINISHED reading task without a primary source: one small LLM call picks one from the canon;
  * for an UNFINISHED hands-on task without acceptance tests: the normal stage-5 generation (suite + reference solution,
    verified in the sandbox).
Notes, submissions and completed work are never touched.

Due dates are SPREAD from today (about two days of old cards per day) instead of using the original dates: backfilling two
weeks at once must not create a wall of overdue cards that locks all new work through the review gate.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from psycopg.types.json import Jsonb

from app.config import Settings, get_settings
from app.curriculum import canon, prompts, repository
from app.curriculum.errors import LLMError
from app.curriculum.schemas import GroundingContext, HandsOnTask, PrimarySourcePick
from app.db import get_pool
from app.mastery import cards

log = logging.getLogger(__name__)


def _spread(card_list: list[dict], today: date, offset: int) -> list[dict]:
    due = today + timedelta(days=offset)
    return [{**c, "due_on": max(c["due_on"], due)} for c in card_list]


def pick_primary_source(llm, settings: Settings, reading: dict) -> dict:
    sources = canon.for_skill(reading["skill_slug"], difficulty=reading.get("difficulty", 2), exclude=repository.used_source_ids())
    pick = llm.generate(system=prompts.PRIMARY_SOURCE_SYSTEM, output_model=PrimarySourcePick, temperature=settings.temp_daily,
                        user=prompts.build_primary_source_prompt(reading["chapter_title"], reading["skill_slug"], reading.get("learning_goals", []), sources),
                        grounding=GroundingContext(frozenset(), frozenset(), source_ids=frozenset(s.id for s in sources)))
    return {**canon.load_canon()[pick.source_id].model_dump(), "focus": pick.focus, "guiding_question": pick.guiding_question}


def backfill(*, days: int = 14, use_llm: bool = True, dry_run: bool = False, llm=None, settings: Settings | None = None,
             today: date | None = None) -> dict:
    from app.curriculum.generators import local_now, write_acceptance_tests

    settings = settings or get_settings()
    today = today or local_now(settings).date()
    since = today - timedelta(days=days)
    stats = {"briefings": 0, "cards": 0, "primary_sources": 0, "acceptance_suites": 0, "skipped_llm": 0, "errors": 0}
    with get_pool().connection() as conn:
        rows = conn.execute(
            """select b.id as bid, b.day, b.payload, t.id, t.kind, t.skill_slug, t.completed_at, t.reading_content, t.acceptance_tests
               from daily_briefings b join daily_tasks t on t.briefing_id = b.id
               where b.day >= %s and b.day <= %s order by b.day, t.kind""", (since, today)).fetchall()
        themes = conn.execute("select week_start, payload from weekly_themes where week_start >= %s and week_start <= %s",
                              (since - timedelta(days=6), today)).fetchall()
    if use_llm and not dry_run and llm is None:
        from app.curriculum.llm import StructuredLLM
        llm = StructuredLLM(settings)

    days_seen = sorted({r["day"] for r in rows})
    stats["briefings"] = len(days_seen)
    new_cards: list[dict] = []
    for r in rows:
        offset = days_seen.index(r["day"]) // 2  # ~2 old lessons' cards per day from today
        payload = r["payload"] or {}
        if r["kind"] == "reading" and r["reading_content"]:
            new_cards += _spread(cards.chapter_cards(task_id=r["id"], day=r["day"], skill_slug=r["skill_slug"], chapter_md=r["reading_content"]), today, offset)
        unfinished = r["completed_at"] is None
        if r["kind"] == "reading" and unfinished and not (payload.get("morning_reading") or {}).get("primary_source") and payload.get("morning_reading"):
            if not use_llm or dry_run:
                stats["skipped_llm"] += 1
            else:
                try:
                    primary = pick_primary_source(llm, settings, payload["morning_reading"])
                except LLMError as exc:
                    log.warning("primary source for %s failed: %s", r["day"], exc)
                    stats["errors"] += 1
                else:
                    with get_pool().connection() as conn:
                        conn.execute("update daily_briefings set payload = jsonb_set(payload, '{morning_reading,primary_source}', %s) where id=%s",
                                     (Jsonb(primary), r["bid"]))
                    new_cards += _spread([cards.primary_source_card(task_id=r["id"], day=r["day"], skill_slug=r["skill_slug"], source=primary)], today, offset)
                    stats["primary_sources"] += 1
        if r["kind"] == "hands_on" and unfinished and r["acceptance_tests"] is None and payload.get("hands_on_task") and settings.acceptance_tests:
            if not use_llm or dry_run:
                stats["skipped_llm"] += 1
            else:
                tests = write_acceptance_tests(llm, settings, HandsOnTask.model_validate(payload["hands_on_task"]))
                if tests is None:
                    stats["errors"] += 1
                else:
                    with get_pool().connection() as conn:
                        conn.execute("update daily_tasks set acceptance_tests=%s, reference_solution=%s where id=%s and acceptance_tests is null",
                                     (Jsonb(tests[0]), Jsonb(tests[1]), r["id"]))
                    stats["acceptance_suites"] += 1
    for t in themes:
        new_cards += _spread(cards.teachback_cards(week_start=t["week_start"], theme=t["payload"]), today, 0)
    if dry_run:
        stats["cards"] = len(new_cards)
        stats["dry_run"] = True
        return stats
    stats["cards"] = repository.save_cards(new_cards)  # only genuinely new cards are inserted (dedupe keys)
    return stats
