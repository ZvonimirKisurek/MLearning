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

from app.curriculum.schemas import HandsOnTask, TaskEvaluationSchema, WeeklyThemeOutput
from app.ingestion.models import Category


class ArticleRefOut(BaseModel):
    article_uuid: str
    ref_id: str | None = Field(default=None, description="the [A7] id used in the text's citations")
    title: str
    url: str
    source: str
    category: str


class PrimarySourceOut(BaseModel):
    id: str
    kind: str
    title: str
    authors: str
    year: int
    locator: str = Field(description="what to read: a chapter, sections, a video")
    url: str | None = Field(description="written by a human in canon.yaml, never by the model; null = search the title")
    level: int
    minutes: int
    summary: str
    focus: str = Field(description="what to read today and what to look for (chosen by the planner)")
    guiding_question: str = Field(description="answer it from memory afterwards; it is also a review card")


class ReadingOut(BaseModel):
    chapter_title: str
    skill_slug: str
    difficulty: int
    learning_goals: list[str]
    estimated_minutes: int
    word_count: int
    section_headings: list[str]
    inspiration: list[ArticleRefOut]
    primary_source: PrimarySourceOut | None = Field(default=None, description="absent on briefings generated before Phase 10")


class InsightOut(BaseModel):
    headline: str
    thesis: str
    skill_slug: str
    body: str = Field(description="the ~500-word analytical essay, markdown")
    word_count: int
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
    attempt_count: int = 0
    evaluation_score: int | None = None
    evaluation_passed: bool | None = None
    has_content: bool = False


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
    quarter: dict | None = Field(default=None, description="the roadmap quarter this week belongs to, with its public deliverable")


class WeeklyThemeBody(WeeklyThemeOutput):
    key_articles: list[ArticleRefOut]
    roadmap: RoadmapInfo | None = None
    math_topics: list[str] | None = Field(default=None, description="this week's math-drill topics (roadmap mode)")


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


class ReadingDetail(ReadingOut):
    content: str | None = Field(description="the full chapter, markdown with LaTeX and fenced code")


class TestReportOut(BaseModel):
    expected: int
    passed: int
    failed: list[str]
    missing: list[str]
    all_passed: bool
    results: dict[str, str]
    summary_line: str | None = None


class EvaluationOut(TaskEvaluationSchema):
    tests: TestReportOut | None = Field(default=None, description="the acceptance-test result folded into the grade (null if the task has no suite)")


class AcceptanceTestsOut(BaseModel):
    path: str
    code: str
    test_names: list[str]
    interface: list[str]
    status: Literal["verified", "unverified"] = Field(description="verified = proven passable against a reference solution in a sandbox")
    detail: str
    run_command: str


class SourceFileOut(BaseModel):
    path: str
    content: str


class TaskDetailOut(BaseModel):
    task: TaskOut
    day: date
    reading: ReadingDetail | None
    hands_on: HandsOnTask | None
    insight: InsightOut | None
    submission: str | None = Field(description="the learner's latest submission")
    evaluation: EvaluationOut | None = Field(description="the latest graded result")
    attempts_used: int
    attempts_max: int
    acceptance_tests: AcceptanceTestsOut | None = Field(default=None, description="the executable suite for a hands-on task")
    test_output: str | None = Field(default=None, description="the pytest output from the latest submission")
    reference_solution: list[SourceFileOut] | None = Field(default=None, description="revealed once the task is passed or every attempt is used")
    notes: str = Field(default="", description="the learner's notebook for this task")
    archived: bool = Field(default=False, description="the task belongs to a past day (in the learner's timezone)")


class NotesIn(BaseModel):
    notes: str = Field(max_length=50000)


class NotesOut(BaseModel):
    notes: str
    updated_at: datetime | None


class SubmissionIn(BaseModel):
    submission: str = Field(min_length=20, max_length=20000, description="your code AND the terminal output of running it")
    test_output: str | None = Field(default=None, max_length=30000, description="the output of `python -m pytest -v <acceptance file>` (required when the task has acceptance tests)")


class SubmissionOut(BaseModel):
    task: TaskOut
    evaluation: EvaluationOut
    passed: bool
    skill: SkillDelta | None = Field(description="set only when the submission passed and moved a skill")
    briefing_completed: bool
    attempts_used: int
    attempts_max: int


# ------------------------------------------------------------------------------------------- mastery loop
class ReviewCardOut(BaseModel):
    id: UUID
    source: Literal["chapter", "teachback", "primary_source"]
    skill_slug: str
    prompt: str
    due_on: date
    reps: int
    lapses: int
    interval_days: float
    ease: float
    task_id: UUID | None
    week_start: date | None
    last_reviewed_at: datetime | None
    has_reference: bool


class ReviewReferenceOut(BaseModel):
    id: UUID
    context: str = Field(description="the text the question was written from")


class RecallIn(BaseModel):
    answer: str = Field(min_length=3, max_length=4000, description="your answer, written from memory")


class RecallOut(BaseModel):
    verdict: Literal["correct", "partial", "incorrect"]
    missing_points: list[str]
    model_answer: str
    feedback: str
    suggested_grade: int = Field(ge=1, le=4)


class GradeIn(BaseModel):
    grade: int = Field(ge=1, le=4, description="1 again, 2 hard, 3 good, 4 easy")
    answer: str = Field(default="", max_length=4000)
    feedback: dict | None = None


class GradeOut(BaseModel):
    card: ReviewCardOut
    next_due: date
    remaining_due: int


class SuspendIn(BaseModel):
    suspended: bool


class ReviewStatsOut(BaseModel):
    due: int
    overdue: int
    active: int
    next_7_days: int
    reviewed_today: int
    reviews_30d: int
    retention_30d: float | None = Field(description="share of reviews graded good/easy in the last 30 days")


class GateOut(BaseModel):
    locked: bool
    reasons: list[str]


class RetroStatusOut(BaseModel):
    week_start: date
    required: bool
    submitted: bool


class MathStatusOut(BaseModel):
    attempted: int
    correct: int
    total: int
    accuracy_30d: float | None


class MasteryOut(BaseModel):
    date: date
    reviews: ReviewStatsOut
    gate: GateOut
    retro: RetroStatusOut
    math: MathStatusOut
    generated_at: datetime


class MilestoneEvidence(BaseModel):
    milestone: str = Field(min_length=1, max_length=500)
    evidence: str = Field(min_length=3, max_length=1000, description="a link, a commit, a number - or 'not done: <why>'")


class RetroIn(BaseModel):
    milestone_evidence: list[MilestoneEvidence] = Field(max_length=12)
    reflection: str = Field(min_length=50, max_length=4000, description="what worked, what did not, what you still cannot explain")
    decision: str = Field(min_length=10, max_length=1000, description="what changes next week; the planner reads it")
    public_artifact_url: str | None = Field(default=None, max_length=500, pattern=r"^https?://\S+$")


class TeachbackItem(BaseModel):
    id: UUID
    prompt: str
    due_on: date
    answered: bool


class KindCount(BaseModel):
    done: int
    total: int


class RetroNumbers(BaseModel):
    tasks_done: int
    tasks_total: int
    by_kind: dict[str, KindCount]
    click_bursts: int = Field(description="windows of 3+ completions within 10 minutes (possible click-through)")
    hands_on_passed: int
    tests_all_passed: int
    math_attempted: int
    math_correct: int
    reviews: int
    review_retention: float | None


class RetroSubmitted(BaseModel):
    submitted_at: datetime
    milestone_evidence: list[MilestoneEvidence]
    reflection: str
    decision: str
    public_artifact_url: str | None


class RetroOut(BaseModel):
    week_start: date
    week_end: date
    required: bool
    submitted: bool
    can_submit: bool
    blockers: list[str]
    theme_title: str | None
    milestones: list[str]
    deliverable: str | None
    quarter: dict | None
    roadmap_week: int | None
    numbers: RetroNumbers
    teachback: list[TeachbackItem]
    retro: RetroSubmitted | None


class MathProblemOut(BaseModel):
    idx: int
    topic: str
    area: str
    prompt: str
    hint: str
    attempted: bool
    correct: bool | None
    answer_given: str | None
    expected: float | None = Field(description="revealed after the first attempt")
    solution: str | None = Field(description="revealed after the first attempt")


class MathDrillOut(BaseModel):
    day: date
    problems: list[MathProblemOut]
    attempted: int
    correct: int
    total: int


class MathAnswerIn(BaseModel):
    answer: str = Field(min_length=1, max_length=60)


class MathAnswerOut(BaseModel):
    idx: int
    correct: bool
    first_attempt: bool
    counted_correct: bool = Field(description="only the first attempt counts")
    expected: float
    solution: str
    skill: SkillDelta | None
