"""Async SQL for the API. Every function takes the request's connection; none opens its own transaction."""
from __future__ import annotations

import base64
import json
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from psycopg import AsyncConnection

from app.config import Settings
from app.curriculum.skills import apply_delta, compute_delta


class BadCursor(ValueError):
    pass


# ----------------------------------------------------------------------------------------------- skills
async def fetch_skills(conn: AsyncConnection) -> list[dict]:
    skills = await (await conn.execute("select slug, name, level, target from skills order by name")).fetchall()
    hist = await (await conn.execute(
        """select s.slug, h.level, h.recorded_at, h.delta from skill_history h join skills s on s.id = h.skill_id
           where h.recorded_at > now() - interval '30 days' order by h.recorded_at""")).fetchall()
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    out = []
    for s in skills:
        points = [h for h in hist if h["slug"] == s["slug"]]
        out.append({
            "slug": s["slug"], "name": s["name"], "level": round(s["level"], 2), "target": s["target"],
            "percent_to_target": round(min(100.0, s["level"] / max(s["target"], 1) * 100), 1),
            "delta_7d": round(sum((h["delta"] or 0) for h in points if h["recorded_at"] >= week_ago), 3),
            "history": [{"at": h["recorded_at"], "level": h["level"]} for h in points],
        })
    return out


# ----------------------------------------------------------------------------------------------- today
async def _tasks(conn: AsyncConnection, briefing_id) -> list[dict]:
    rows = await (await conn.execute(
        """select id, kind, skill_slug, difficulty, title, completed_at, points_awarded from daily_tasks
           where briefing_id=%s order by case kind when 'reading' then 1 when 'hands_on' then 2 else 3 end""",
        (briefing_id,))).fetchall()
    return [{**r, "completed": r["completed_at"] is not None} for r in rows]


async def fetch_today(conn: AsyncConnection, day: date) -> dict:
    b = await (await conn.execute("select id, day, completed_at, payload, theme_id from daily_briefings where day=%s", (day,))).fetchone()
    week_start = day - timedelta(days=day.weekday())
    t = await (await conn.execute("select id, week_start, payload from weekly_themes where week_start=%s", (week_start,))).fetchone()
    return {
        "date": day,
        "state": "ready" if b else "pending",
        "briefing": None if b is None else {"id": b["id"], "day": b["day"], "completed_at": b["completed_at"],
                                            "payload": b["payload"], "tasks": await _tasks(conn, b["id"])},
        "weekly_theme": None if t is None else {"id": t["id"], "week_start": t["week_start"], "theme": t["payload"]},
        "skills": await fetch_skills(conn),
    }


# ----------------------------------------------------------------------------------------------- completion
async def complete_task(conn: AsyncConnection, task_id: UUID) -> dict | None:
    """Mark a task done and move its skill - atomically, idempotently, and safe under concurrency.

    * The conditional UPDATE (`completed_at is null`) is the idempotency guard. Two simultaneous requests
      both try it; Postgres lets one proceed and makes the other WAIT on the row lock, then re-evaluates the
      condition, finds it false, and updates zero rows. Exactly one request wins and awards points.
    * `select ... for update` on the skill row serialises read-modify-write of the level (two different tasks
      on the same skill completed at the same instant must not overwrite each other's increment).
    * All of this runs in the request's transaction (Conn dependency): it commits together or not at all.
    """
    task = await (await conn.execute(
        "update daily_tasks set completed_at=now() where id=%s and completed_at is null "
        "returning id, briefing_id, kind, skill_slug, difficulty", (task_id,))).fetchone()
    if task is None:
        row = await (await conn.execute("select briefing_id, points_awarded, skill_slug from daily_tasks where id=%s", (task_id,))).fetchone()
        if row is None:
            return None
        skill = await (await conn.execute("select level from skills where slug=%s", (row["skill_slug"],))).fetchone()
        done = await (await conn.execute("select completed_at is not null as d from daily_briefings where id=%s", (row["briefing_id"],))).fetchone()
        return await _completion(conn, task_id, row["skill_slug"], float(row["points_awarded"] or 0), float(skill["level"]), done["d"], True)

    skill = await (await conn.execute("select level from skills where slug=%s for update", (task["skill_slug"],))).fetchone()
    delta = compute_delta(task["kind"], task["difficulty"], float(skill["level"]))
    new_level = apply_delta(float(skill["level"]), delta)
    await conn.execute("update skills set level=%s, updated_at=now() where slug=%s", (new_level, task["skill_slug"]))
    await conn.execute("update daily_tasks set points_awarded=%s where id=%s", (delta, task_id))
    await conn.execute("insert into skill_history (skill_id, level, delta, task_id) select id, %s, %s, %s from skills where slug=%s",
                       (new_level, delta, task_id, task["skill_slug"]))
    remaining = (await (await conn.execute(
        "select count(*) as n from daily_tasks where briefing_id=%s and completed_at is null", (task["briefing_id"],))).fetchone())["n"]
    if remaining == 0:
        await conn.execute("update daily_briefings set completed_at=now() where id=%s", (task["briefing_id"],))
    return await _completion(conn, task_id, task["skill_slug"], delta, new_level, remaining == 0, False)


async def _completion(conn, task_id, slug, delta, level, briefing_done, already) -> dict:
    task = await (await conn.execute(
        "select id, kind, skill_slug, difficulty, title, completed_at, points_awarded from daily_tasks where id=%s", (task_id,))).fetchone()
    return {"task": {**task, "completed": task["completed_at"] is not None},
            "skill": {"slug": slug, "level": round(level, 3), "delta": delta},
            "briefing_completed": briefing_done, "already_completed": already}


async def briefing_exists(conn: AsyncConnection, day: date) -> bool:
    return await (await conn.execute("select 1 from daily_briefings where day=%s", (day,))).fetchone() is not None


# ----------------------------------------------------------------------------------------------- feed
def _encode(sort: str, key, row_id) -> str:
    return base64.urlsafe_b64encode(json.dumps([sort, key.isoformat() if isinstance(key, datetime) else key, str(row_id)]).encode()).decode()


def _decode(cursor: str, sort: str):
    try:
        s, key, rid = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        if s != sort:
            raise ValueError("cursor belongs to a different sort order")
        return (datetime.fromisoformat(key) if sort == "recent" else float(key)), UUID(rid)
    except Exception as exc:
        raise BadCursor("invalid cursor") from exc


def _strength(sim: float, s: Settings) -> str:
    return "strong" if sim >= s.match_strong else "moderate" if sim >= s.match_moderate else "weak"


async def fetch_feed(
    conn: AsyncConnection, settings: Settings, *, category: str | None, skill: str | None, sort: str,
    limit: int, cursor: str | None, days: int,
) -> dict:
    """Keyset-paginated feed of canonical (de-duplicated) articles.

    Dedup in the data flow: ingestion stored near-identical stories with `duplicate_of` pointing at the first
    one seen; here `duplicate_of is null` hides the copies and `also_covered_by` reports which other sources
    carried the story - so the UI can show "also on The Verge, TechCrunch" instead of five rows.

    Relevance in the data flow: the LATERAL subquery finds, per article, the nearest skill vector by cosine
    distance (`<=>`). similarity = 1 - distance. `relevance = similarity * (0.5 + 0.5 * gap)` boosts matches to
    skills where you are furthest from target. Cosine values for article-vs-skill-description text are
    typically 0.15-0.5, NOT percentages: the API therefore also returns a coarse `strength` bucket whose
    thresholds you calibrate with `python -m app.cli feed-stats`.

    Keyset vs OFFSET: `OFFSET 1000` makes Postgres read and discard 1000 rows, and rows inserted meanwhile shift
    the pages (duplicates/skips). Keyset resumes strictly after the last (sort_key, id) seen - stable and fast.
    """
    key = "ts" if sort == "recent" else "relevance"
    params: dict = {"since": datetime.now(timezone.utc) - timedelta(days=days), "limit": limit + 1}
    inner = ["a.duplicate_of is null", "coalesce(a.published_at, a.fetched_at) >= %(since)s"]
    outer = []
    if category:
        inner.append("s.category = %(category)s")
        params["category"] = category
    if skill:
        outer.append("best_skill = %(skill)s")
        params["skill"] = skill
    if cursor:
        params["ck"], params["cid"] = _decode(cursor, sort)
        outer.append(f"({key}, id) < (%(ck)s::{'timestamptz' if sort == 'recent' else 'double precision'}, %(cid)s::uuid)")
    sql = f"""
      select * from (
        select a.id, a.title, a.url, a.summary, a.ai_summary, a.engagement,
               coalesce(a.published_at, a.fetched_at) as ts,
               s.slug as source_slug, s.name as source_name, s.category,
               best.slug as best_skill, best.name as best_skill_name, best.sim::double precision as similarity,
               coalesce(best.sim * (0.5 + 0.5 * best.gap), 0)::double precision as relevance,
               array(select distinct s2.name from articles d join sources s2 on s2.id = d.source_id
                     where d.duplicate_of = a.id order by s2.name) as also_covered_by
        from articles a join sources s on s.id = a.source_id
        left join lateral (
          select k.slug, k.name, 1 - (a.embedding <=> k.embedding) as sim,
                 greatest(0, least(1, (k.target - k.level) / greatest(k.target, 1))) as gap
          from skills k where k.embedding is not null and a.embedding is not null
          order by a.embedding <=> k.embedding limit 1
        ) best on true
        where {' and '.join(inner)}
      ) f
      {'where ' + ' and '.join(outer) if outer else ''}
      order by {key} desc, id desc limit %(limit)s"""
    rows = await (await conn.execute(sql, params)).fetchall()
    more = len(rows) > limit
    rows = rows[:limit]
    items = [{
        "id": r["id"], "title": r["title"], "url": r["url"], "source_slug": r["source_slug"], "source_name": r["source_name"],
        "category": r["category"], "published_at": r["ts"], "summary": r["summary"], "ai_summary": r["ai_summary"],
        "engagement": r["engagement"], "relevance": round(r["relevance"], 4), "also_covered_by": r["also_covered_by"],
        "skill_match": None if r["best_skill"] is None else {
            "skill_slug": r["best_skill"], "skill_name": r["best_skill_name"], "similarity": round(r["similarity"], 4),
            "strength": _strength(r["similarity"], settings)},
    } for r in rows]
    nxt = _encode(sort, rows[-1]["ts"] if sort == "recent" else rows[-1]["relevance"], rows[-1]["id"]) if more and rows else None
    return {"items": items, "next_cursor": nxt}
