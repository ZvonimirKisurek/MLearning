from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.concurrency import run_in_threadpool

from app.api import queries
from app.api.deps import Cfg, Conn, get_enqueue, require_token
from app.api.schemas import CompletionOut, FeedPage, QueueOut, SkillOut, TodayOut
from app.ingestion.models import Category

# Auth applies to the whole router; /health lives outside it.
router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])


def _today(cfg) -> "datetime.date":
    return datetime.now(ZoneInfo(cfg.timezone)).date()


@router.get("/today", response_model=TodayOut)
async def today(conn: Conn, cfg: Cfg):
    """Everything the Command Center needs in one round trip. `state="pending"` (briefing null) is a normal,
    expected response before 06:30 or if generation failed - it is NOT an error, so it is a 200."""
    return await queries.fetch_today(conn, _today(cfg))


@router.post("/tasks/{task_id}/complete", response_model=CompletionOut)
async def complete_task(task_id: UUID, conn: Conn):
    """Idempotent: completing twice returns `already_completed: true` and awards nothing the second time."""
    result = await queries.complete_task(conn, task_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "task not found")
    return result


@router.get("/skills", response_model=list[SkillOut])
async def skills(conn: Conn):
    return await queries.fetch_skills(conn)


@router.get("/feed", response_model=FeedPage)
async def feed(
    conn: Conn, cfg: Cfg,
    category: Annotated[Category | None, Query(description="research | industry_news | engineering_blog | community | newsletter | researcher")] = None,
    skill: Annotated[str | None, Query(max_length=40, pattern=r"^[a-z0-9-]+$", description="only articles whose best-matching skill is this slug")] = None,
    sort: Literal["recent", "relevance"] = "recent",
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    days: Annotated[int, Query(ge=1, le=60)] = 14,
):
    try:
        return await queries.fetch_feed(conn, cfg, category=category, skill=skill, sort=sort, limit=limit, cursor=cursor, days=days)
    except queries.BadCursor as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("/briefing/generate", response_model=QueueOut, status_code=status.HTTP_202_ACCEPTED)
async def generate_briefing(conn: Conn, cfg: Cfg, enqueue: Annotated[Callable[[str], None], Depends(get_enqueue)]):
    """For the empty state: ask a Celery worker to generate today's briefing now. Returns immediately (202);
    the UI polls /api/today. LLM generation takes tens of seconds - never do that inside a request."""
    if await queries.briefing_exists(conn, _today(cfg)):
        return QueueOut(queued=False, reason="already generated")
    try:
        # `enqueue` is blocking network I/O (a Redis connection). Calling it directly inside `async def` would
        # freeze the event loop - and every other request - while it waits. Offload blocking calls to a thread.
        await run_in_threadpool(enqueue, "app.tasks.generate_daily_briefing")
    except Exception as exc:  # broker down
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "task queue unavailable") from exc
    return QueueOut(queued=True)
