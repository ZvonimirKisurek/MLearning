import { Skeleton } from "@/components/ui/skeleton";

export const ReadingSkeleton = () => (
  <div aria-busy="true" aria-label="Loading chapter" className="max-w-3xl space-y-5">
    <Skeleton className="h-4 w-40" /><Skeleton className="h-12 w-3/4" /><Skeleton className="h-4 w-1/2" /><Skeleton className="h-32 w-full rounded-2xl" />
    {Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-5 w-full" />)}
  </div>
);

export const PracticeSkeleton = () => (
  <div aria-busy="true" aria-label="Loading workspace" className="grid gap-8 lg:grid-cols-2">
    <div className="space-y-5"><Skeleton className="h-10 w-2/3" />{[0, 1, 2].map((i) => <Skeleton key={i} className="h-48 rounded-2xl" />)}</div>
    <Skeleton className="h-[34rem] rounded-2xl" />
  </div>
);
