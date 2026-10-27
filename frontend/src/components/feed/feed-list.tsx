"use client";

import { useState, useTransition } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { FeedItem, FeedPage } from "@/lib/types";
import { ArticleCard } from "./article-card";

/**
 * The first page is rendered on the server (fast first paint, no spinner). "Load more" appends further pages
 * client-side by calling our same-origin /api/feed proxy with the opaque keyset cursor the API gave us.
 * The parent passes `key={query}`, so changing a filter remounts this component and resets its state.
 */
export function FeedList({ initial, query }: { initial: FeedPage; query: string }) {
  const [items, setItems] = useState<FeedItem[]>(initial.items);
  const [cursor, setCursor] = useState<string | null>(initial.next_cursor);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function loadMore() {
    if (!cursor) return;
    setError(null);
    start(async () => {
      try {
        const qs = new URLSearchParams(query);
        qs.set("cursor", cursor);
        const res = await fetch(`/api/feed?${qs}`);
        if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error ?? `HTTP ${res.status}`);
        const page: FeedPage = await res.json();
        setItems((prev) => {
          const seen = new Set(prev.map((i) => i.id)); // guard against a page overlapping after new ingestion
          return [...prev, ...page.items.filter((i) => !seen.has(i.id))];
        });
        setCursor(page.next_cursor);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load more");
      }
    });
  }

  if (items.length === 0)
    return (
      <div className="rounded-lg border border-dashed p-10 text-center">
        <p className="font-medium">No articles match these filters</p>
        <p className="mt-1 text-sm text-muted-foreground">Try &quot;All&quot; / &quot;Any&quot;, or run <code className="font-mono">python -m app.cli ingest</code> to fetch more.</p>
      </div>
    );

  return (
    <div className="space-y-3">
      <ul className="space-y-3">{items.map((i) => <li key={i.id}><ArticleCard item={i} /></li>)}</ul>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      <div className="flex justify-center pt-2">
        {cursor ? (
          <Button variant="outline" onClick={loadMore} disabled={pending}>
            {pending && <Loader2 className="animate-spin" />} Load more
          </Button>
        ) : (
          <p className="font-mono text-xs text-muted-foreground">end of feed · {items.length} articles</p>
        )}
      </div>
    </div>
  );
}
