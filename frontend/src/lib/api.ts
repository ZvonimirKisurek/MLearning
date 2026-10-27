import "server-only";

import type { Completion, FeedPage, FeedQuery, Skill, Today } from "./types";

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

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      cache: "no-store", // personal, live data: never serve a stale briefing or completion state
      signal: AbortSignal.timeout(15_000),
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
export const getSkills = () => request<Skill[]>("/api/skills");
export const completeTask = (id: string) => request<Completion>(`/api/tasks/${id}/complete`, { method: "POST" });
export const queueBriefing = () => request<{ queued: boolean; reason: string | null }>("/api/briefing/generate", { method: "POST" });

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
