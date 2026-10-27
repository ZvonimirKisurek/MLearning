"use client"; // Recharts measures the DOM and animates, so it must run in the browser

import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer, Tooltip } from "recharts";
import { TrendingUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { skillLabel } from "@/lib/skills";
import type { Skill } from "@/lib/types";


export function SkillProgress({ skills }: { skills: Skill[] }) {
  const data = skills.map((s) => ({ label: skillLabel(s.slug), level: s.level, target: s.target }));
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <TrendingUp className="size-4 text-primary" /> Skill matrix
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[260px]" role="img" aria-label={`Radar chart of skill levels versus targets: ${data.map((d) => `${d.label} ${d.level.toFixed(0)} of ${d.target}`).join(", ")}`}>
          <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 340, height: 260 }}>
            <RadarChart data={data} outerRadius="78%">
              <PolarGrid stroke="var(--border)" />
              <PolarAngleAxis dataKey="label" tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} />
              <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
              <Radar name="Target" dataKey="target" stroke="var(--muted-foreground)" strokeDasharray="4 4" fill="none" isAnimationActive={false} />
              <Radar name="Level" dataKey="level" stroke="var(--primary)" strokeWidth={2} fill="var(--primary)" fillOpacity={0.22} />
              <Tooltip
                formatter={(v) => (typeof v === "number" ? v.toFixed(1) : String(v))}
                contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
                itemStyle={{ color: "var(--foreground)" }}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>
        {/* The chart is a summary; this list carries the exact numbers (and is what screen readers use). */}
        <ul className="mt-2 space-y-3">
          {skills.map((s) => (
            <li key={s.slug}>
              <div className="mb-1 flex items-baseline justify-between text-xs">
                <span className="font-medium">{skillLabel(s.slug)}</span>
                <span className="font-mono text-muted-foreground">
                  {s.level.toFixed(1)} <span className="opacity-60">/ {s.target.toFixed(0)}</span>
                  {s.delta_7d > 0 && <span className="ml-2 text-primary">+{s.delta_7d.toFixed(1)} 7d</span>}
                </span>
              </div>
              <div className="relative h-1.5 rounded-full bg-muted" role="progressbar" aria-valuenow={s.percent_to_target} aria-valuemin={0} aria-valuemax={100} aria-label={`${skillLabel(s.slug)} progress to target`}>
                <div className="h-full rounded-full bg-primary transition-all duration-700" style={{ width: `${Math.min(100, s.level)}%` }} />
                <div className="absolute top-1/2 h-3 w-px -translate-y-1/2 bg-muted-foreground/70" style={{ left: `${s.target}%` }} title={`Target ${s.target}`} />
              </div>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
