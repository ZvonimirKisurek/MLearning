import type { Metadata } from "next";
import { Suspense } from "react";
import { ApiProblem } from "@/components/api-problem";
import { FeedFilters } from "@/components/feed/feed-filters";
import { FeedList } from "@/components/feed/feed-list";
import { Skeleton } from "@/components/ui/skeleton";
import { attempt, getFeed, getSkills } from "@/lib/api";
import type { Category, FeedQuery } from "@/lib/types";

export const metadata: Metadata = { title: "Intelligence Feed" };

const CATEGORIES = ["research", "industry_news", "engineering_blog", "community", "newsletter", "researcher"];
type SearchParams = Promise<Record<string, string | string[] | undefined>>;

const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v);

/**
 * `searchParams` is runtime (per-request) data, so under Cache Components it must be read inside <Suspense>.
 * The page itself stays static (header + skeleton paint instantly); <FeedContent> streams in.
 */
export default function FeedPage({ searchParams }: { searchParams: SearchParams }) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Intelligence Feed</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          De-duplicated articles from 130+ sources, ranked against your skill gaps with embeddings.
        </p>
      </div>
      <Suspense fallback={<FeedSkeleton />}>
        <FeedContent searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

async function FeedContent({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  // Validate untrusted URL input before it goes anywhere near the API.
  const category = one(sp.category);
  const skill = one(sp.skill);
  const sort = one(sp.sort);
  const params = {
    category: category && CATEGORIES.includes(category) ? category : undefined,
    skill: skill && /^[a-z0-9-]{1,40}$/.test(skill) ? skill : undefined,
    sort: sort === "relevance" ? "relevance" : undefined,
  };
  const q: FeedQuery = { category: params.category as Category | undefined, skill: params.skill, sort: params.sort as FeedQuery["sort"] };

  const [data, err] = await attempt(Promise.all([getFeed(q), getSkills()])); // parallel, not sequential
  if (!data) return <ApiProblem error={err} />;
  const [page, skills] = data;
  const query = new URLSearchParams(Object.entries(params).filter(([, v]) => v) as [string, string][]).toString();
  return (
    <>
      <FeedFilters params={params} skills={skills} />
      <FeedList key={query} initial={page} query={query} />
    </>
  );
}

function FeedSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading feed" className="space-y-4">
      <div className="space-y-2.5">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-6 w-2/3" />)}</div>
      {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-36 rounded-lg" />)}
    </div>
  );
}
