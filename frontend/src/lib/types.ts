/** Mirrors backend/app/api/schemas.py. */
export type TaskKind = "reading" | "hands_on" | "insight";
export type Category = "research" | "industry_news" | "engineering_blog" | "community" | "newsletter" | "researcher";

export interface ArticleRef { article_uuid: string; ref_id?: string | null; title: string; url: string; source: string; category: string }

export interface Task {
  id: string; kind: TaskKind; skill_slug: string; difficulty: number; title: string;
  completed: boolean; completed_at: string | null; points_awarded: number | null;
  attempt_count: number; evaluation_score: number | null; evaluation_passed: boolean | null; has_content: boolean;
}

export interface RubricCriterion { name: string; description: string; max_points: number; must_pass: boolean }
export interface Rubric { pass_score: number; criteria: RubricCriterion[] }
export interface HandsOnStep { title: string; instructions: string; commands: string[]; expected_output: string }

export interface HandsOnSpec {
  title: string; skill_slug: string; difficulty: number; objective: string; prerequisites: string[]; project_layout: string[];
  steps: HandsOnStep[]; deliverable: string; submission_instructions: string; docs_to_consult: string[];
  estimated_minutes: number; stretch_goal: string | null; rubric: Rubric;
}

/** A human-written primary source from backend/curriculum/canon.yaml, picked by the planner for the day. */
export interface PrimarySource {
  id: string; kind: "paper" | "book" | "course" | "video" | "blog" | "doc"; title: string; authors: string; year: number;
  locator: string; url: string | null; level: number; minutes: number; summary: string; focus: string; guiding_question: string;
}

export interface ReadingMeta {
  chapter_title: string; skill_slug: string; difficulty: number; learning_goals: string[]; estimated_minutes: number;
  word_count: number; section_headings: string[]; inspiration: ArticleRef[];
  /** Absent on briefings generated before the mastery loop existed. */
  primary_source?: PrimarySource | null;
}
export interface InsightMeta {
  headline: string; thesis: string; skill_slug: string; body: string; word_count: number; evidence: ArticleRef[];
}

export interface Briefing {
  id: string; day: string; completed_at: string | null; tasks: Task[];
  payload: { morning_reading: ReadingMeta; hands_on_task: HandsOnSpec; market_insight: InsightMeta };
}

export interface DayPlan {
  day: number; focus: string; skill_slug: string; intensity: "light" | "normal" | "stretch";
  reading_hint: string; build_hint: string;
}
export interface Quarter { index: number; title: string; weeks: [number, number]; public_deliverable: string; success_criteria: string[] }
export interface RoadmapInfo { index: number; of: number; title: string; goal: string; deliverable: string; milestones: string[]; quarter?: Quarter | null }

export interface WeeklyTheme {
  id: string; week_start: string;
  theme: {
    title: string; rationale: string; seminar_overview: string; core_questions: string[]; market_signals: string[]; focus_skills: string[];
    learning_objectives: string[]; key_articles: ArticleRef[]; daily_plan: DayPlan[]; roadmap: RoadmapInfo | null;
    math_topics?: string[] | null;
  };
}

export interface Skill {
  slug: string; name: string; level: number; target: number; percent_to_target: number; delta_7d: number;
  history: { at: string; level: number }[];
}

export interface Today { date: string; state: "ready" | "pending"; briefing: Briefing | null; weekly_theme: WeeklyTheme | null; skills: Skill[] }

export interface Completion {
  task: Task; skill: { slug: string; level: number; delta: number }; briefing_completed: boolean; already_completed: boolean;
}

export interface CriterionResult { criterion: string; points: number; max_points: number; evidence: string }
/** The acceptance-test result, parsed by code from the learner's `pytest -v` output. */
export interface TestReport {
  expected: number; passed: number; failed: string[]; missing: string[]; all_passed: boolean;
  results: Record<string, string>; summary_line: string | null;
}
export interface Evaluation {
  criteria: CriterionResult[]; score: number; passed: boolean; summary: string; strengths: string[]; problems: string[];
  how_to_improve: string[]; feedback_markdown: string; tests?: TestReport | null;
}
export interface AcceptanceTests {
  path: string; code: string; test_names: string[]; interface: string[];
  status: "verified" | "unverified"; detail: string; run_command: string;
}
export interface SubmissionResult {
  task: Task; evaluation: Evaluation; passed: boolean; skill: { slug: string; level: number; delta: number } | null;
  briefing_completed: boolean; attempts_used: number; attempts_max: number;
}

export interface TaskDetail {
  task: Task; day: string; attempts_used: number; attempts_max: number;
  reading: (ReadingMeta & { content: string | null }) | null;
  hands_on: HandsOnSpec | null; insight: InsightMeta | null;
  submission: string | null; evaluation: Evaluation | null;
  /** True when the task belongs to a past day: it stays readable but can no longer be submitted. */
  archived: boolean;
  /** The learner's notebook text for this task ("" if none). */
  notes: string;
  acceptance_tests?: AcceptanceTests | null;
  test_output?: string | null;
  /** Revealed once the task is passed or every attempt is used. */
  reference_solution?: { path: string; content: string }[] | null;
}

// ------------------------------------------------------------------------------------- mastery loop
export type CardSource = "chapter" | "teachback" | "primary_source";
export interface ReviewCard {
  id: string; source: CardSource; skill_slug: string; prompt: string; due_on: string; reps: number; lapses: number;
  interval_days: number; ease: number; task_id: string | null; week_start: string | null; last_reviewed_at: string | null; has_reference: boolean;
}
export interface RecallCheck { verdict: "correct" | "partial" | "incorrect"; missing_points: string[]; model_answer: string; feedback: string; suggested_grade: number }
export interface GradeResult { card: ReviewCard; next_due: string; remaining_due: number }

export interface Mastery {
  date: string;
  reviews: { due: number; overdue: number; active: number; next_7_days: number; reviewed_today: number; reviews_30d: number; retention_30d: number | null };
  gate: { locked: boolean; reasons: string[] };
  retro: { week_start: string; required: boolean; submitted: boolean };
  math: { attempted: number; correct: number; total: number; accuracy_30d: number | null };
  /** Unfinished lessons from recent past days that can still be done (late). */
  catchup?: CatchupItem[];
}
export interface CatchupItem {
  id: string; kind: TaskKind; title: string; skill_slug: string; attempt_count: number; day: string; has_tests: boolean; expires_on: string;
}

export interface MilestoneEvidence { milestone: string; evidence: string }
export interface Retro {
  week_start: string; week_end: string; required: boolean; submitted: boolean; can_submit: boolean; blockers: string[];
  theme_title: string | null; milestones: string[]; deliverable: string | null; quarter: Quarter | null; roadmap_week: number | null;
  numbers: {
    tasks_done: number; tasks_total: number; by_kind: Record<string, { done: number; total: number }>; click_bursts: number;
    hands_on_passed: number; tests_all_passed: number; math_attempted: number; math_correct: number; reviews: number; review_retention: number | null;
  };
  teachback: { id: string; prompt: string; due_on: string; answered: boolean }[];
  retro: { submitted_at: string; milestone_evidence: MilestoneEvidence[]; reflection: string; decision: string; public_artifact_url: string | null } | null;
}
export interface RetroInput { milestone_evidence: MilestoneEvidence[]; reflection: string; decision: string; public_artifact_url: string | null }

export interface MathProblem {
  idx: number; topic: string; area: string; prompt: string; hint: string; attempted: boolean; correct: boolean | null;
  answer_given: string | null; expected: number | null; solution: string | null;
}
export interface MathDrill { day: string; problems: MathProblem[]; attempted: number; correct: number; total: number }
export interface MathAnswer {
  idx: number; correct: boolean; first_attempt: boolean; counted_correct: boolean; expected: number; solution: string;
  skill: { slug: string; level: number; delta: number } | null;
}

export interface SkillMatch { skill_slug: string; skill_name: string; similarity: number; strength: "strong" | "moderate" | "weak" }

export interface FeedItem {
  id: string; title: string; url: string; source_slug: string; source_name: string; category: Category;
  published_at: string; summary: string | null; ai_summary: string | null; engagement: number | null;
  skill_match: SkillMatch | null; relevance: number; also_covered_by: string[];
}

export interface FeedPage { items: FeedItem[]; next_cursor: string | null }
export interface FeedQuery { category?: Category; skill?: string; sort?: "recent" | "relevance"; min_strength?: "moderate" | "strong"; cursor?: string; limit?: number }
