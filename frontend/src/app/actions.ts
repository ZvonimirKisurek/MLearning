"use server";

import { refresh } from "next/cache";
import { ApiError, completeTask, queueBriefing, saveNotes, submitTask } from "@/lib/api";
import type { Completion, SubmissionResult } from "@/lib/types";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export type ActionResult<T> = { ok: true; data: T } | { ok: false; error: string };

const message = (e: unknown) => (e instanceof ApiError ? e.message : "Unexpected error");

/**
 * Server Actions are public HTTP endpoints under the hood: treat arguments as untrusted and validate them.
 * `refresh()` re-renders this page's Server Components so every consumer (checklist, progress, skill chart)
 * gets fresh data from the API in the same round trip as the action's response.
 */
export async function completeTaskAction(taskId: string): Promise<ActionResult<Completion>> {
  if (!UUID.test(taskId)) return { ok: false, error: "Invalid task id" };
  try {
    const data = await completeTask(taskId);
    refresh();
    return { ok: true, data };
  } catch (e) {
    return { ok: false, error: message(e) };
  }
}

export async function generateBriefingAction(): Promise<ActionResult<{ queued: boolean }>> {
  try {
    const r = await queueBriefing();
    if (!r.queued) refresh(); // "already generated": the page just needs to re-render
    return { ok: true, data: { queued: r.queued } };
  } catch (e) {
    return { ok: false, error: message(e) };
  }
}

/**
 * Submit hands-on work for AI grading. The skill matrix moves only if the (verified) grade passes; on a pass we
 * refresh() so every server-rendered view that shows skills or task state is re-fetched.
 */
export async function submitTaskAction(taskId: string, submission: string): Promise<ActionResult<SubmissionResult>> {
  if (!UUID.test(taskId)) return { ok: false, error: "Invalid task id" };
  if (submission.trim().length < 20) return { ok: false, error: "Paste your code and its output first (at least 20 characters)." };
  if (submission.length > 20_000) return { ok: false, error: "That is over the 20,000-character limit." };
  try {
    const data = await submitTask(taskId, submission);
    refresh();
    return { ok: true, data };
  } catch (e) {
    return { ok: false, error: message(e) };
  }
}

/**
 * Notebook auto-save. Deliberately NO refresh(): re-rendering the chapter on every pause in typing would be wasteful
 * and could disturb scroll position. The client already holds the text it just sent.
 */
export async function saveNotesAction(taskId: string, notes: string): Promise<ActionResult<{ updatedAt: string | null }>> {
  if (!UUID.test(taskId)) return { ok: false, error: "Invalid task id" };
  if (notes.length > 50_000) return { ok: false, error: "Notes are limited to 50,000 characters." };
  try {
    const r = await saveNotes(taskId, notes);
    return { ok: true, data: { updatedAt: r.updated_at } };
  } catch (e) {
    return { ok: false, error: message(e) };
  }
}
