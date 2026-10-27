/** Mirrors backend/app/api/schemas.py. (Generate from /openapi.json with `openapi-typescript` if you prefer.) */
export type TaskKind = "reading" | "hands_on" | "insight";
export type Category = "research" | "industry_news" | "engineering_blog" | "community" | "newsletter" | "researcher";

export interface ArticleRef { article_uuid: string; title: string; url: string; source: string; category: string }

export interface Task {
  id: string; kind: TaskKind; skill_slug: string; difficulty: number; title: string;
  completed: boolean; completed_at: string | null; points_awarded: number | null;
}

export interface Briefing {
  id: string; day: string; completed_at: string | null; tasks: Task[];
  payload: {
    morning_reading: ArticleRef & {
      article_id: string; skill_slug: string; difficulty: number; why_it_matters: string;
      guiding_questions: string[]; estimated_minutes: number;
    };
    hands_on_task: {
      title: string; skill_slug: string; difficulty: number; objective: string; prerequisites: string[];
      steps: string[]; deliverable: string; docs_to_consult: string[]; estimated_minutes: number; stretch_goal: string | null;
    };
    market_insight: {
      headline: string; body: string; career_angle: string; skill_slug: string;
      evidence_article_ids: string[]; evidence: ArticleRef[];
    };
  };
}

export interface DayPlan {
  day: number; focus: string; skill_slug: string; intensity: "light" | "normal" | "stretch";
  reading_hint: string; build_hint: string;
}

export interface RoadmapInfo { index: number; of: number; title: string; goal: string; deliverable: string; milestones: string[] }

export interface WeeklyTheme {
  id: string; week_start: string;
  theme: {
    title: string; rationale: string; market_signals: string[]; focus_skills: string[];
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

export interface SkillMatch { skill_slug: string; skill_name: string; similarity: number; strength: "strong" | "moderate" | "weak" }

export interface FeedItem {
  id: string; title: string; url: string; source_slug: string; source_name: string; category: Category;
  published_at: string; summary: string | null; ai_summary: string | null; engagement: number | null;
  skill_match: SkillMatch | null; relevance: number; also_covered_by: string[];
}

export interface FeedPage { items: FeedItem[]; next_cursor: string | null }
export interface FeedQuery { category?: Category; skill?: string; sort?: "recent" | "relevance"; min_strength?: "moderate" | "strong"; cursor?: string; limit?: number }
