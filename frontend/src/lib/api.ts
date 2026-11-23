import "server-only";

import type {
  Completion, FeedPage, FeedQuery, GradeResult, Mastery, MathAnswer, MathDrill, RecallCheck, Retro, RetroInput, ReviewCard, Skill,
  SubmissionResult, TaskDetail, Today,
} from "./types";

/**
 * Server-side client for the FastAPI backend.
 *
 * `server-only` makes the build fail if a Client Component ever imports this file, so API_TOKEN can never
 * ship to the browser. The browser talks only to Next.js; Next.js (server components, server actions, the
 * /api/feed route handler) talks to FastAPI. That is why the backend needs no browser-facing auth and why
 * CORS never comes into play on the main path.
 */
const BASE = process.env.API_URL ?? "http://localhost:8000";
const TOKEN = process.env.API_TOKEN ?? "";

export type ApiErrorKind = "network" | "auth" | "client" | "server";

export class ApiError extends Error {
  constructor(public kind: ApiErrorKind, public status: number | null, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init: RequestInit = {}, timeoutMs = 15_000): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      cache: "no-store", // personal, live data: never serve a stale briefing or completion state
      signal: AbortSignal.timeout(timeoutMs),
      headers: { "Content-Type": "application/json", ...(TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}), ...init.headers },
    });
  } catch {
    throw new ApiError("network", null, `Cannot reach the API at ${BASE}. Is uvicorn running?`);
  }
  if (!res.ok) {
    const detail = await res.json().then((j) => (typeof j.detail === "string" ? j.detail : "")).catch(() => "");
    if (res.status === 401) throw new ApiError("auth", 401, "The API rejected API_TOKEN. Check it matches the backend's API_TOKEN.");
    throw new ApiError(res.status >= 500 ? "server" : "client", res.status, detail || `API error ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const getToday = () => request<Today>("/api/today");
/** Every YYYY-MM-DD that has a stored briefing (oldest first). Drives which calendar cells are clickable. */
export const getHistory = () => request<string[]>("/api/briefings/history");
/** One day's briefing, same shape as getToday(). Rejects with ApiError(status 404) for a date with no stored briefing. */
export const getDay = (date: string) => request<Today>(`/api/briefings/${date}`);
export const getSkills = () => request<Skill[]>("/api/skills");
export const completeTask = (id: string) => request<Completion>(`/api/tasks/${id}/complete`, { method: "POST" });
export const getTask = (id: string) => request<TaskDetail>(`/api/tasks/${id}`);
/** Grading is an LLM call that can take 10-60 s, so this one request gets a long timeout. */
export const submitTask = (id: string, submission: string, testOutput?: string) =>
  request<SubmissionResult>(`/api/tasks/${id}/submit`, { method: "POST", body: JSON.stringify({ submission, test_output: testOutput || null }) }, 150_000);
export const saveNotes = (id: string, notes: string) =>
  request<{ notes: string; updated_at: string | null }>(`/api/tasks/${id}/notes`, { method: "PUT", body: JSON.stringify({ notes }) });
export const queueBriefing = () => request<{ queued: boolean; reason: string | null }>("/api/briefing/generate", { method: "POST" });

// ---------------------------------------------------------------------------- mastery loop
export const getMastery = () => request<Mastery>("/api/mastery");
export const getReviews = (limit?: number) => request<ReviewCard[]>(`/api/reviews${limit ? `?limit=${limit}` : ""}`);
export const getReviewReference = (id: string) => request<{ id: string; context: string }>(`/api/reviews/${id}/reference`);
/** An LLM call (a few seconds); schedules nothing. */
export const checkReview = (id: string, answer: string) =>
  request<RecallCheck>(`/api/reviews/${id}/check`, { method: "POST", body: JSON.stringify({ answer }) }, 90_000);
export const gradeReview = (id: string, grade: number, answer: string, feedback: RecallCheck | null) =>
  request<GradeResult>(`/api/reviews/${id}/grade`, { method: "POST", body: JSON.stringify({ grade, answer, feedback }) });
export const suspendReview = (id: string, suspended: boolean) =>
  request<ReviewCard>(`/api/reviews/${id}/suspend`, { method: "POST", body: JSON.stringify({ suspended }) });
export const getRetro = (weekStart: string) => request<Retro>(`/api/retro/${weekStart}`);
export const putRetro = (weekStart: string, body: RetroInput) => request<Retro>(`/api/retro/${weekStart}`, { method: "PUT", body: JSON.stringify(body) });
export const getMath = () => request<MathDrill>("/api/math/today");
export const answerMath = (day: string, idx: number, answer: string) =>
  request<MathAnswer>(`/api/math/${day}/${idx}/answer`, { method: "POST", body: JSON.stringify({ answer }) });

export function getFeed(q: FeedQuery) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(q)) if (v !== undefined && v !== "") p.set(k, String(v));
  return request<FeedPage>(`/api/feed?${p}`);
}

/** Await a promise into a [value, error] tuple so Server Components can branch without JSX inside try/catch. */
export async function attempt<T>(p: Promise<T>): Promise<[T, null] | [null, unknown]> {
  try {
    return [await p, null];
  } catch (e) {
    return [null, e];
  }
}
