import { Skeleton } from "@/components/ui/skeleton";

export function CommandCenterSkeleton() {
  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_380px]" aria-busy="true" aria-label="Loading dashboard">
      <div className="space-y-6">
        <div className="flex items-end justify-between"><Skeleton className="h-7 w-44" /><Skeleton className="h-4 w-40" /></div>
        {[0, 1, 2].map((i) => <Skeleton key={i} className="h-28 rounded-lg" />)}
        <Skeleton className="h-72 rounded-lg" />
      </div>
      <Skeleton className="h-[34rem] rounded-lg" />
    </div>
  );
}
