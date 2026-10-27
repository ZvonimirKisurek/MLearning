"use client"; // error boundaries must be Client Components

import { useEffect } from "react";
import { AlertTriangle, RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * Route-level error boundary: catches anything thrown while rendering this segment (an unexpected 500 from the
 * API, a schema mismatch...). Expected problems (API down, bad token) are handled inline by <ApiProblem/>; this is
 * the safety net. In production, Server Component errors arrive with a generic message + `digest`, to avoid
 * leaking internals - match the digest against server logs.
 */
export default function RouteError({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => console.error(error), [error]);
  return (
    <div className="mx-auto max-w-md rounded-lg border border-destructive/30 bg-destructive/5 p-6 text-center">
      <AlertTriangle className="mx-auto mb-3 size-6 text-destructive" />
      <h2 className="font-semibold">Something went wrong</h2>
      <p className="mt-1 text-sm text-muted-foreground">The page failed to render. This is usually temporary.</p>
      {error.digest && <p className="mt-2 font-mono text-xs text-muted-foreground">ref: {error.digest}</p>}
      <Button className="mt-4" variant="outline" onClick={() => retry()}>
        <RotateCw /> Try again
      </Button>
    </div>
  );
}
