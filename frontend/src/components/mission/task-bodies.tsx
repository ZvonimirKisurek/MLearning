import { ArrowUpRight, Target } from "lucide-react";
import type { ArticleRef, Briefing } from "@/lib/types";

const H = ({ children }: { children: React.ReactNode }) => (
  <h4 className="mb-1.5 mt-4 font-mono text-[10px] font-medium uppercase tracking-widest text-muted-foreground first:mt-0">{children}</h4>
);

export function ExternalLink({ href, children }: { href: string; children: React.ReactNode }) {
  // Links come from our database, never from LLM text. rel hardens against window.opener / referrer leaks.
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-info underline-offset-4 hover:underline">
      {children}
      <ArrowUpRight className="size-3.5" />
    </a>
  );
}

const Evidence = ({ items }: { items: ArticleRef[] }) => (
  <ul className="space-y-1 text-sm">
    {items.map((a) => (
      <li key={a.article_uuid} className="flex gap-2">
        <span className="text-muted-foreground">{a.source}</span>
        <ExternalLink href={a.url}>{a.title}</ExternalLink>
      </li>
    ))}
  </ul>
);

export function ReadingBody({ r }: { r: Briefing["payload"]["morning_reading"] }) {
  return (
    <div className="text-sm leading-relaxed">
      <p className="mb-3 text-muted-foreground">
        {r.source} · <ExternalLink href={r.url}>Open article</ExternalLink>
      </p>
      <H>Why it matters</H>
      <p>{r.why_it_matters}</p>
      <H>While reading, answer</H>
      <ul className="list-disc space-y-1 pl-5 marker:text-muted-foreground">
        {r.guiding_questions.map((q) => <li key={q}>{q}</li>)}
      </ul>
    </div>
  );
}

export function HandsOnBody({ h }: { h: Briefing["payload"]["hands_on_task"] }) {
  return (
    <div className="text-sm leading-relaxed">
      <p>{h.objective}</p>
      {h.prerequisites.length > 0 && (
        <>
          <H>Prerequisites</H>
          <ul className="flex flex-wrap gap-1.5">
            {h.prerequisites.map((p) => <li key={p} className="rounded-md bg-muted px-2 py-0.5 text-xs">{p}</li>)}
          </ul>
        </>
      )}
      <H>Steps</H>
      <ol className="list-decimal space-y-1.5 pl-5 marker:font-mono marker:text-muted-foreground">
        {h.steps.map((s) => <li key={s}>{s}</li>)}
      </ol>
      <div className="mt-4 flex gap-2 rounded-md border border-primary/20 bg-primary/5 p-3">
        <Target className="mt-0.5 size-4 shrink-0 text-primary" />
        <div><span className="font-medium text-primary">Deliverable: </span>{h.deliverable}</div>
      </div>
      {h.docs_to_consult.length > 0 && (
        <>
          <H>Check the official docs for</H>
          <ul className="flex flex-wrap gap-1.5">
            {h.docs_to_consult.map((d) => <li key={d} className="rounded-md border px-2 py-0.5 font-mono text-xs">{d}</li>)}
          </ul>
        </>
      )}
      {h.stretch_goal && (<><H>Stretch goal</H><p className="text-muted-foreground">{h.stretch_goal}</p></>)}
    </div>
  );
}

export function InsightBody({ m }: { m: Briefing["payload"]["market_insight"] }) {
  return (
    <div className="text-sm leading-relaxed">
      <p>{m.body}</p>
      <H>Why it matters for your career</H>
      <p className="text-muted-foreground">{m.career_angle}</p>
      <H>Evidence</H>
      <Evidence items={m.evidence} />
    </div>
  );
}
