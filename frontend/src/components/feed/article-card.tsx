import { ArrowUpRight, Layers, Sparkles, TrendingUp } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { Category, FeedItem } from "@/lib/types";
import { cn, formatDate } from "@/lib/utils";

export const CATEGORY_LABEL: Record<Category, string> = {
  research: "Research", industry_news: "Industry", engineering_blog: "Engineering",
  community: "Community", newsletter: "Newsletter", researcher: "Researcher",
};

const STRENGTH = {
  strong: { variant: "primary", label: "strong match" },
  moderate: { variant: "info", label: "related" },
  weak: { variant: "default", label: "loose match" },
} as const;

/**
 * One feed row. Reading the badges tells you WHY the article is here:
 *  - skill badge   : the skill whose description is closest to this article in embedding space (cosine similarity).
 *                    "strong/related/loose" are buckets over that similarity, not percentages - hover for the raw value.
 *  - "also on N"   : the de-duplicator found the same story from N other sources and collapsed them into this row.
 *  - engagement    : HN points / HF upvotes / stars-today, when the source reports it.
 */
export function ArticleCard({ item }: { item: FeedItem }) {
  const m = item.skill_match;
  const s = m ? STRENGTH[m.strength] : null;
  return (
    <article className="rounded-lg border bg-card p-4 transition-colors hover:border-input">
      <div className="mb-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
        <span className="font-medium text-foreground/80">{item.source_name}</span>
        <span aria-hidden>·</span>
        <time dateTime={item.published_at}>{formatDate(item.published_at)}</time>
        <Badge variant="outline">{CATEGORY_LABEL[item.category]}</Badge>
      </div>

      <h3 className="text-[15px] font-semibold leading-snug">
        <a href={item.url} target="_blank" rel="noopener noreferrer" className="hover:text-primary hover:underline underline-offset-4">
          {item.title}
        </a>
      </h3>

      {item.ai_summary ? (
        <p className="mt-2 text-sm leading-relaxed">
          <span className="mr-1.5 inline-flex items-center gap-1 align-middle font-mono text-[10px] uppercase tracking-widest text-violet">
            <Sparkles className="size-3" /> AI summary
          </span>
          {item.ai_summary}
        </p>
      ) : item.summary ? (
        <p className="mt-2 line-clamp-3 text-sm leading-relaxed text-muted-foreground" title="Excerpt from the source feed (no AI summary yet)">
          {item.summary}
        </p>
      ) : null}

      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        {m && s && (
          <Badge
            variant={s.variant}
            title={`Cosine similarity to your "${m.skill_name}" skill profile: ${m.similarity.toFixed(3)}. Higher = closer in meaning.`}
          >
            {m.skill_name} · {s.label}
          </Badge>
        )}
        {item.also_covered_by.length > 0 && (
          <Badge variant="violet" title={`Same story also reported by: ${item.also_covered_by.join(", ")}`}>
            <Layers className="size-3" /> also on {item.also_covered_by.length}
          </Badge>
        )}
        {item.engagement ? (
          <Badge variant="warn" title="Community engagement (points / upvotes / stars)">
            <TrendingUp className="size-3" /> {item.engagement.toLocaleString("en-US")}
          </Badge>
        ) : null}
        <a
          href={item.url} target="_blank" rel="noopener noreferrer"
          className={cn("ml-auto inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground")}
        >
          Read original <ArrowUpRight className="size-3.5" />
        </a>
      </div>
    </article>
  );
}
