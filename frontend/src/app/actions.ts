"use server";

import { refresh } from "next/cache";
import {
  ApiError, answerMath, checkReview, completeTask, getReviewReference, getTask, gradeReview, putRetro, queueBriefing, saveNotes, submitTask,
  suspendReview,
} from "@/lib/api";
import type { Completion, GradeResult, MathAnswer, RecallCheck, Retro, RetroInput, SubmissionResult } from "@/lib/types";

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
export async function submitTaskAction(taskId: string, submission: string, testOutput?: string): Promise<ActionResult<SubmissionResult>> {
  if (!UUID.test(taskId)) return { ok: false, error: "Invalid task id" };
  if (submission.trim().length < 20) return { ok: false, error: "Paste your code and its output first (at least 20 characters)." };
  if (submission.length > 20_000) return { ok: false, error: "That is over the 20,000-character limit." };
  if (testOutput && testOutput.length > 30_000) return { ok: false, error: "The pytest output is over 30,000 characters; paste only the -v run." };
  try {
    const data = await submitTask(taskId, submission, testOutput);
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

/** Loads what the global notebook needs for any chapter or lab: its title and the saved notes. */
export async function loadNotebookAction(taskId: string): Promise<ActionResult<{ title: string; notes: string }>> {
  if (!UUID.test(taskId)) return { ok: false, error: "Invalid task id" };
  try {
    const d = await getTask(taskId);
    return { ok: true, data: { title: d.reading?.chapter_title ?? d.hands_on?.title ?? "Notes", notes: d.notes } };
  } catch (e) {
    return { ok: false, error: message(e) };
  }
}

// ---------------------------------------------------------------------------- mastery loop
const DATE = /^\d{4}-\d{2}-\d{2}$/;

/** AI check of an answer written from memory. No refresh(): nothing is scheduled until the learner grades. */
export async function checkReviewAction(cardId: string, answer: string): Promise<ActionResult<RecallCheck>> {
  if (!UUID.test(cardId)) return { ok: false, error: "Invalid card id" };
  if (answer.trim().length < 3) return { ok: false, error: "Write your answer first." };
  try {
    return { ok: true, data: await checkReview(cardId, answer.slice(0, 4000)) };
  } catch (e) {
    return { ok: false, error: message(e) };
  }
}

export async function revealReferenceAction(cardId: string): Promise<ActionResult<string>> {
  if (!UUID.test(cardId)) return { ok: false, error: "Invalid card id" };
  try {
    return { ok: true, data: (await getReviewReference(cardId)).context };
  } catch (e) {
    return { ok: false, error: message(e) };
  }
}

/** No refresh() here: the review session advances client-side; the summary re-renders when the queue is empty. */
export async function gradeReviewAction(cardId: string, grade: number, answer: string, feedback: RecallCheck | null): Promise<ActionResult<GradeResult>> {
  if (!UUID.test(cardId)) return { ok: false, error: "Invalid card id" };
  if (![1, 2, 3, 4].includes(grade)) return { ok: false, error: "Invalid grade" };
  try {
    return { ok: true, data: await gradeReview(cardId, grade, answer.slice(0, 4000), feedback) };
  } catch (e) {
    return { ok: false, error: message(e) };
  }
}

export async function suspendReviewAction(cardId: string): Promise<ActionResult<null>> {
  if (!UUID.test(cardId)) return { ok: false, error: "Invalid card id" };
  try {
    await suspendReview(cardId, true);
    return { ok: true, data: null };
  } catch (e) {
    return { ok: false, error: message(e) };
  }
}

export async function submitRetroAction(weekStart: string, body: RetroInput): Promise<ActionResult<Retro>> {
  if (!DATE.test(weekStart)) return { ok: false, error: "Invalid week" };
  if (body.reflection.trim().length < 50) return { ok: false, error: "Write at least 50 characters of reflection." };
  if (body.decision.trim().length < 10) return { ok: false, error: "Write the decision for next week (at least 10 characters)." };
  try {
    const data = await putRetro(weekStart, { ...body, public_artifact_url: body.public_artifact_url?.trim() || null });
    refresh();
    return { ok: true, data };
  } catch (e) {
    return { ok: false, error: message(e) };
  }
}

export async function answerMathAction(day: string, idx: number, answer: string): Promise<ActionResult<MathAnswer>> {
  if (!DATE.test(day) || !Number.isInteger(idx) || idx < 0 || idx > 9) return { ok: false, error: "Invalid problem" };
  if (!answer.trim()) return { ok: false, error: "Enter a number." };
  try {
    const data = await answerMath(day, idx, answer.trim().slice(0, 60));
    refresh();  // the drill header and the dashboard tile re-render; each problem card keeps its own client state
    return { ok: true, data };
  } catch (e) {
    return { ok: false, error: message(e) };
  }
}
