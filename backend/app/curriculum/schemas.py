"""Pydantic schemas = the *contract* between the LLM and our database.

WHY STRUCTURED OUTPUT?
An LLM is a next-token predictor; left alone it returns prose. We need data a program can store and a
UI can render, so we demand JSON that matches a schema. Two independent layers enforce it:

  1. Constrained decoding (server side). The JSON Schema is sent in `output_config.format`. The API compiles it
     into a grammar and, at every decoding step, masks tokens that would break it. The model *cannot* emit
     malformed JSON or a missing field. This guarantees SHAPE only.
  2. Pydantic validation (client side, below). The API cannot enforce what a JSON Schema cannot express:
     length limits, ranges, list sizes, and - most importantly - *grounding*: "this article id must be one
     of the 50 we showed you". Failures here trigger a repair re-prompt (see llm.py).

Why Pydantic rather than hand-written checks? One class gives us (a) the JSON Schema we send to the API,
(b) parsing + type coercion, (c) precise, machine-readable error locations we can feed back to the model
so it can fix exactly what was wrong. Constraints the API grammar does not support (min/max, length) are
stripped from the wire schema by `anthropic.transform_schema` and enforced here instead.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, ValidationInfo, model_validator


@dataclass(frozen=True)
class GroundingContext:
    """Closed-world facts passed to `model_validate(..., context=...)`.

    Anything the model references must come from these sets. This is the core anti-hallucination device:
    the model never types a URL or a paper title that we then trust; it can only *point at* ids we gave it.
    """

    article_ids: frozenset[str]  # short ids shown in the prompt, e.g. "A7"
    skill_slugs: frozenset[str]


def _grounding(info: ValidationInfo) -> GroundingContext | None:
    return info.context if isinstance(info.context, GroundingContext) else None


def _article_id(v: str, info: ValidationInfo) -> str:
    g = _grounding(info)
    if g is not None and v not in g.article_ids:
        raise ValueError(f"{v!r} is not one of the provided article ids (use only ids that appear in <articles>)")
    return v


def _skill_slug(v: str, info: ValidationInfo) -> str:
    g = _grounding(info)
    if g is not None and v not in g.skill_slugs:
        raise ValueError(f"{v!r} is not a known skill slug; allowed: {sorted(g.skill_slugs)}")
    return v


def _no_urls(v: str) -> str:
    # Links come from our database, never from the model. A URL in generated text is, by construction,
    # something the model recalled or invented - reject it and let the repair loop remove it.
    if "http://" in v or "https://" in v or "www." in v:
        raise ValueError("do not include URLs; refer to sources by article id or by library/function name")
    return v


ArticleRef = Annotated[str, AfterValidator(_article_id)]
SkillSlug = Annotated[str, AfterValidator(_skill_slug)]
Text = Annotated[str, AfterValidator(_no_urls)]


class _Strict(BaseModel):
    # extra="forbid" -> `additionalProperties: false` in the schema, which the API requires.
    model_config = ConfigDict(extra="forbid")


# ------------------------------------------------------------------------------ weekly theme
class DayPlan(_Strict):
    day: int = Field(ge=1, le=7, description="ISO weekday: 1=Monday ... 7=Sunday")
    focus: Text = Field(max_length=140, description="One-line focus for the day, e.g. 'Write a training loop from scratch'")
    skill_slug: SkillSlug
    intensity: Literal["light", "normal", "stretch"] = Field(description="Weekend days should be light")
    reading_hint: Text = Field(max_length=200, description="What kind of article would fit this day")
    build_hint: Text = Field(max_length=200, description="What kind of small coding task would fit this day")


class WeeklyThemeOutput(_Strict):
    title: Text = Field(max_length=90, description="Theme title, e.g. 'Building RAG pipelines with PyTorch and pgvector'")
    rationale: Text = Field(max_length=900, description="Why this theme, this week, for this learner; cite market signals")
    market_signals: list[Text] = Field(min_length=2, max_length=5, description="Concrete trends seen in the supplied articles")
    focus_skills: list[SkillSlug] = Field(min_length=1, max_length=3)
    learning_objectives: list[Text] = Field(min_length=3, max_length=5, description="Observable outcomes by Sunday")
    key_article_ids: list[ArticleRef] = Field(min_length=3, max_length=10, description="Articles that best evidence the theme")
    daily_plan: list[DayPlan] = Field(min_length=7, max_length=7, description="Exactly one entry per weekday 1..7")

    @model_validator(mode="after")
    def _days_complete(self) -> WeeklyThemeOutput:
        if sorted(d.day for d in self.daily_plan) != list(range(1, 8)):
            raise ValueError("daily_plan must contain each day 1..7 exactly once")
        return self


# ------------------------------------------------------------------------------ daily briefing
class MorningReading(_Strict):
    article_id: ArticleRef
    skill_slug: SkillSlug
    difficulty: int = Field(ge=1, le=3, description="1=accessible, 3=research-level")
    why_it_matters: Text = Field(max_length=400)
    guiding_questions: list[Text] = Field(min_length=2, max_length=4, description="Questions to answer while reading")
    estimated_minutes: int = Field(ge=5, le=45)


class HandsOnTask(_Strict):
    title: Text = Field(max_length=100)
    skill_slug: SkillSlug
    difficulty: int = Field(ge=1, le=3)
    objective: Text = Field(max_length=300)
    prerequisites: list[Text] = Field(max_length=4, description="Things to have installed/known; may be empty")
    steps: list[Text] = Field(min_length=3, max_length=8, description="Concrete ordered steps")
    deliverable: Text = Field(max_length=250, description="A checkable artifact: a script, a passing test, a plot")
    docs_to_consult: list[Text] = Field(max_length=4, description="Official docs by library + symbol name, no URLs; may be empty")
    estimated_minutes: int = Field(ge=15, le=90)
    stretch_goal: Text | None = Field(description="Optional extension, or null")


class MarketInsight(_Strict):
    headline: Text = Field(max_length=120)
    body: Text = Field(max_length=700, description="What is happening, grounded in the supplied articles")
    career_angle: Text = Field(max_length=400, description="Why it matters for an engineer moving into ML engineering")
    skill_slug: SkillSlug = Field(description="The skill this insight most relates to")
    evidence_article_ids: list[ArticleRef] = Field(min_length=1, max_length=4)


class DailyBriefingOutput(_Strict):
    morning_reading: MorningReading
    hands_on_task: HandsOnTask
    market_insight: MarketInsight

    @model_validator(mode="after")
    def _time_budget(self) -> DailyBriefingOutput:
        total = self.morning_reading.estimated_minutes + self.hands_on_task.estimated_minutes
        if total > 120:
            raise ValueError(f"reading + hands-on must fit in 120 minutes, got {total}")
        return self


# ------------------------------------------------------------------------------ article summaries
class ArticleSummary(_Strict):
    id: ArticleRef
    summary: Text = Field(max_length=360, description="1-2 neutral sentences using only the supplied title and excerpt")


class SummaryBatch(_Strict):
    summaries: list[ArticleSummary]

    @model_validator(mode="after")
    def _covers_every_article(self, info: ValidationInfo) -> SummaryBatch:
        g = _grounding(info)
        ids = [s.id for s in self.summaries]
        if len(ids) != len(set(ids)) or (g is not None and set(ids) != set(g.article_ids)):
            raise ValueError("return exactly one summary for every supplied article id, each once")
        return self
