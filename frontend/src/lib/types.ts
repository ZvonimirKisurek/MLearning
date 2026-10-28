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

export interface ReadingMeta {
  chapter_title: string; skill_slug: string; difficulty: number; learning_goals: string[]; estimated_minutes: number;
  word_count: number; section_headings: string[]; inspiration: ArticleRef[];
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
export interface RoadmapInfo { index: number; of: number; title: string; goal: string; deliverable: string; milestones: string[] }

export interface WeeklyTheme {
  id: string; week_start: string;
  theme: {
    title: string; rationale: string; seminar_overview: string; core_questions: string[]; market_signals: string[]; focus_skills: string[];
    learning_objectives: string[]; key_articles: ArticleRef[]; daily_plan: DayPlan[]; roadmap: RoadmapInfo | null;
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
export interface Evaluation {
  criteria: CriterionResult[]; score: number; passed: boolean; summary: string; strengths: string[]; problems: string[];
  how_to_improve: string[]; feedback_markdown: string;
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
}

export interface SkillMatch { skill_slug: string; skill_name: string; similarity: number; strength: "strong" | "moderate" | "weak" }

export interface FeedItem {
  id: string; title: string; url: string; source_slug: string; source_name: string; category: Category;
  published_at: string; summary: string | null; ai_summary: string | null; engagement: number | null;
  skill_match: SkillMatch | null; relevance: number; also_covered_by: string[];
}

export interface FeedPage { items: FeedItem[]; next_cursor: string | null }
export interface FeedQuery { category?: Category; skill?: string; sort?: "recent" | "relevance"; min_strength?: "moderate" | "strong"; cursor?: string; limit?: number }
