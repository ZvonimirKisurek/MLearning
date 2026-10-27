"use client";

import { useOptimistic, useState, useTransition } from "react";
import { BookOpen, ChevronDown, Clock, Hammer, Lightbulb, PartyPopper, TriangleAlert } from "lucide-react";
import { completeTaskAction } from "@/app/actions";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { skillLabel } from "@/lib/skills";
import type { Briefing, Task, TaskKind } from "@/lib/types";
import { cn } from "@/lib/utils";
import { HandsOnBody, InsightBody, ReadingBody } from "./task-bodies";

const META: Record<TaskKind, { label: string; icon: typeof BookOpen; tone: string }> = {
  reading: { label: "Morning reading", icon: BookOpen, tone: "text-info" },
  hands_on: { label: "Hands-on", icon: Hammer, tone: "text-primary" },
  insight: { label: "Market insight", icon: Lightbulb, tone: "text-warn" },
};

const Difficulty = ({ n }: { n: number }) => (
  <span className="inline-flex items-center gap-0.5" title={`Difficulty ${n}/3`} aria-label={`Difficulty ${n} of 3`}>
    {[1, 2, 3].map((i) => <span key={i} className={cn("size-1.5 rounded-full", i <= n ? "bg-foreground/70" : "bg-border")} />)}
  </span>
);

/**
 * Client Component: it owns interaction (optimistic checkbox state). The data arrives as props from a Server
 * Component, so the page's first paint contains the real tasks with no client-side fetch/spinner.
 *
 * Optimistic UI, step by step:
 *   1. User ticks a box -> inside a transition we call `markDone(id)`: React instantly renders the optimistic copy.
 *   2. The Server Action runs (API call -> DB transaction -> refresh()).
 *   3. When the transition ends React drops the optimistic layer and shows the real props, which by then are the
 *      refreshed server data. If the action failed, props are unchanged, so the tick visibly rolls back.
 */
export function MissionBoard({ briefing }: { briefing: Briefing }) {
  const [tasks, markDone] = useOptimistic(briefing.tasks, (current: Task[], id: string) =>
    current.map((t) => (t.id === id ? { ...t, completed: true } : t)),
  );
  const [, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [gain, setGain] = useState<Record<string, string>>({});

  const done = tasks.filter((t) => t.completed).length;
  const firstOpen = tasks.find((t) => !t.completed)?.id;
  const p = briefing.payload;

  function complete(task: Task) {
    setError(null);
    startTransition(async () => {
      markDone(task.id);
      const res = await completeTaskAction(task.id);
      if (!res.ok) return setError(res.error);
      if (!res.data.already_completed)
        setGain((g) => ({ ...g, [task.id]: `+${res.data.skill.delta.toFixed(2)} ${skillLabel(res.data.skill.slug)}` }));
    });
  }

  const title = (t: Task) =>
    t.kind === "reading" ? p.morning_reading.title : t.kind === "hands_on" ? p.hands_on_task.title : p.market_insight.headline;
  const minutes = (t: Task) =>
    t.kind === "reading" ? p.morning_reading.estimated_minutes : t.kind === "hands_on" ? p.hands_on_task.estimated_minutes : null;

  return (
    <section aria-labelledby="mission-h">
      <div className="mb-4 flex items-end justify-between">
        <h2 id="mission-h" className="text-xl font-semibold tracking-tight">Today&apos;s Mission</h2>
        <div className="flex items-center gap-3">
          <span className="font-mono text-xs text-muted-foreground">{done}/{tasks.length} complete</span>
          <div className="h-1.5 w-28 overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuenow={done} aria-valuemin={0} aria-valuemax={tasks.length}>
            <div className="h-full rounded-full bg-primary transition-all duration-500" style={{ width: `${(done / tasks.length) * 100}%` }} />
          </div>
        </div>
      </div>

      {error && (
        <div role="alert" className="mb-3 flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          <TriangleAlert className="size-4" /> Couldn&apos;t save that: {error}
        </div>
      )}

      <ul className="space-y-3">
        {tasks.map((t) => {
          const m = META[t.kind];
          const Icon = m.icon;
          const min = minutes(t);
          return (
            <li key={t.id} className={cn("rounded-lg border bg-card transition-opacity", t.completed && "opacity-70")}>
              <div className="flex items-start gap-3 p-4">
                <Checkbox
                  className="mt-0.5"
                  checked={t.completed}
                  disabled={t.completed} // completion is append-only (it moved your skill); there is deliberately no undo
                  onCheckedChange={(v) => v === true && complete(t)}
                  aria-label={`Mark "${title(t)}" complete`}
                />
                <div className="min-w-0 flex-1">
                  <div className={cn("mb-1 flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest", m.tone)}>
                    <Icon className="size-3.5" /> {m.label}
                  </div>
                  <p className={cn("font-medium leading-snug", t.completed && "line-through decoration-muted-foreground/50")}>{title(t)}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <Badge variant="outline">{skillLabel(t.skill_slug)}</Badge>
                    {t.kind !== "insight" && <Difficulty n={t.difficulty} />}
                    {min && <span className="inline-flex items-center gap-1 text-xs text-muted-foreground"><Clock className="size-3" />{min} min</span>}
                    {gain[t.id] && <Badge variant="primary">{gain[t.id]}</Badge>}
                  </div>
                </div>
              </div>
              <details open={t.id === firstOpen} className="group border-t">
                <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-2 text-xs text-muted-foreground hover:text-foreground">
                  Details <ChevronDown className="size-4 transition-transform group-open:rotate-180" />
                </summary>
                <div className="px-4 pb-4 pt-1">
                  {t.kind === "reading" && <ReadingBody r={p.morning_reading} />}
                  {t.kind === "hands_on" && <HandsOnBody h={p.hands_on_task} />}
                  {t.kind === "insight" && <InsightBody m={p.market_insight} />}
                </div>
              </details>
            </li>
          );
        })}
      </ul>

      {done === tasks.length && (
        <p className="mt-4 flex items-center gap-2 rounded-md border border-primary/20 bg-primary/5 px-3 py-2 text-sm text-primary">
          <PartyPopper className="size-4" /> Mission complete. See you tomorrow.
        </p>
      )}
    </section>
  );
}
