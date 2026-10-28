import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { ApiProblem } from "@/components/api-problem";
import { ReadingSkeleton } from "@/components/practice/skeletons";
import { ReadingView } from "@/components/reading/reading-view";
import { ApiError, attempt, getTask } from "@/lib/api";

export const metadata: Metadata = { title: "Chapter" };

/** `params` is per-request data, so (with Cache Components) it is read inside <Suspense>; the shell paints first. */
export default function ReadPage({ params }: { params: Promise<{ taskId: string }> }) {
  return <Suspense fallback={<ReadingSkeleton />}><Content params={params} /></Suspense>;
}

async function Content({ params }: { params: Promise<{ taskId: string }> }) {
  const { taskId } = await params;
  const [detail, err] = await attempt(getTask(taskId));
  if (err instanceof ApiError && (err.status === 404 || err.status === 422)) notFound();
  if (!detail) return <ApiProblem error={err} />;
  if (!detail.reading) notFound();
  return <ReadingView detail={detail} />;
}
