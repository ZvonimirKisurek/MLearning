import { CalendarDays, Compass } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { skillLabel } from "@/lib/skills";
import type { WeeklyTheme } from "@/lib/types";
import { cn, isoWeekday } from "@/lib/utils";
import { ExternalLink } from "./task-bodies";

const DAY = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

/** Pure Server Component: no interactivity, so it ships zero JavaScript to the browser. */
export function WeeklyThemeCard({ weekly, today }: { weekly: WeeklyTheme; today: string }) {
  const t = weekly.theme;
  const todayIdx = isoWeekday(today);
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest text-violet">
          <Compass className="size-3.5" /> This week&apos;s theme
        </div>
        <CardTitle className="text-lg leading-snug">{t.title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <p className="leading-relaxed text-muted-foreground">{t.rationale}</p>
        <div className="flex flex-wrap gap-1.5">
          {t.focus_skills.map((s) => <Badge key={s} variant="violet">{skillLabel(s)}</Badge>)}
        </div>
        <ul className="space-y-1">
          {t.learning_objectives.map((o) => (
            <li key={o} className="flex gap-2"><span className="mt-2 size-1 shrink-0 rounded-full bg-violet" />{o}</li>
          ))}
        </ul>
        <div>
          <div className="mb-2 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
            <CalendarDays className="size-3" /> Plan
          </div>
          <ol className="grid grid-cols-7 gap-1.5">
            {t.daily_plan.map((d) => (
              <li
                key={d.day}
                title={`${d.focus} (${skillLabel(d.skill_slug)}, ${d.intensity})`}
                className={cn("rounded-md border p-1.5 text-center", d.day === todayIdx ? "border-primary bg-primary/10" : "bg-muted/40", d.intensity === "light" && "opacity-70")}
              >
                <div className="font-mono text-[10px] text-muted-foreground">{DAY[d.day - 1]}</div>
                <div className="mt-0.5 truncate text-[10px] leading-tight">{skillLabel(d.skill_slug)}</div>
              </li>
            ))}
          </ol>
          {t.daily_plan.find((d) => d.day === todayIdx) && (
            <p className="mt-2 text-xs text-muted-foreground">Today: {t.daily_plan.find((d) => d.day === todayIdx)?.focus}</p>
          )}
        </div>
        {t.market_signals.length > 0 && (
          <div>
            <div className="mb-1.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Market signals</div>
            <ul className="list-disc space-y-1 pl-5 marker:text-muted-foreground">{t.market_signals.map((s) => <li key={s}>{s}</li>)}</ul>
          </div>
        )}
        {t.key_articles.length > 0 && (
          <div>
            <div className="mb-1.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Evidence</div>
            <ul className="space-y-1">
              {t.key_articles.map((a) => (
                <li key={a.article_uuid} className="flex gap-2"><span className="text-muted-foreground">{a.source}</span><ExternalLink href={a.url}>{a.title}</ExternalLink></li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
