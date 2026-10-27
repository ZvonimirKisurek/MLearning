"""API response models.

Pydantic plays two roles in this app, with the same machinery:
  * LLM boundary (curriculum/schemas.py): an untrusted, probabilistic producer must satisfy a contract.
  * HTTP boundary (this file): FastAPI uses `response_model` to (1) serialise, (2) DROP any field not declared
    (nothing leaks accidentally, e.g. raw embeddings), (3) validate what we send, and (4) generate the
    OpenAPI schema the frontend's TypeScript types mirror.
The briefing models below *inherit* the LLM output models, so the shape the model is asked to produce and the
shape the UI receives cannot drift apart - one source of truth, extended with the fields our code added
(real URLs resolved from article ids).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.curriculum.schemas import HandsOnTask, MarketInsight, MorningReading, WeeklyThemeOutput
from app.ingestion.models import Category


class ArticleRefOut(BaseModel):
    article_uuid: str
    title: str
    url: str
    source: str
    category: str


class ReadingOut(MorningReading, ArticleRefOut): ...


class InsightOut(MarketInsight):
    evidence: list[ArticleRefOut]


class BriefingPayloadOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    morning_reading: ReadingOut
    hands_on_task: HandsOnTask
    market_insight: InsightOut


class TaskOut(BaseModel):
    id: UUID
    kind: Literal["reading", "hands_on", "insight"]
    skill_slug: str
    difficulty: int
    title: str
    completed: bool
    completed_at: datetime | None
    points_awarded: float | None


class BriefingOut(BaseModel):
    id: UUID
    day: date
    completed_at: datetime | None
    payload: BriefingPayloadOut
    tasks: list[TaskOut]


class RoadmapInfo(BaseModel):
    index: int
    of: int
    title: str
    goal: str
    deliverable: str
    milestones: list[str]


class WeeklyThemeBody(WeeklyThemeOutput):
    key_articles: list[ArticleRefOut]
    roadmap: RoadmapInfo | None = None


class WeeklyThemeOut(BaseModel):
    id: UUID
    week_start: date
    theme: WeeklyThemeBody


class HistoryPoint(BaseModel):
    at: datetime
    level: float


class SkillOut(BaseModel):
    slug: str
    name: str
    level: float
    target: float
    percent_to_target: float = Field(description="level / target * 100, capped at 100")
    delta_7d: float = Field(description="points gained in the last 7 days")
    history: list[HistoryPoint]


class TodayOut(BaseModel):
    date: date
    state: Literal["ready", "pending"] = Field(description="'pending' = no briefing generated yet for today")
    briefing: BriefingOut | None
    weekly_theme: WeeklyThemeOut | None
    skills: list[SkillOut]


class SkillDelta(BaseModel):
    slug: str
    level: float
    delta: float


class CompletionOut(BaseModel):
    task: TaskOut
    skill: SkillDelta
    briefing_completed: bool
    already_completed: bool


class SkillMatch(BaseModel):
    skill_slug: str
    skill_name: str
    similarity: float = Field(description="cosine similarity between the article and the skill description, -1..1")
    strength: Literal["strong", "moderate", "weak"]


class FeedItem(BaseModel):
    id: UUID
    title: str
    url: str
    source_slug: str
    source_name: str
    category: Category
    published_at: datetime
    summary: str | None = Field(description="the feed's own excerpt")
    ai_summary: str | None = Field(description="LLM rewrite of title+excerpt; null until the summariser has run")
    engagement: int | None
    skill_match: SkillMatch | None = Field(description="best-matching skill; null if embeddings are missing")
    relevance: float = Field(description="similarity weighted by how big that skill's gap is; used by sort=relevance")
    also_covered_by: list[str] = Field(description="other sources whose near-identical story was collapsed into this one")


class FeedPage(BaseModel):
    items: list[FeedItem]
    next_cursor: str | None


class QueueOut(BaseModel):
    queued: bool
    reason: str | None = None
