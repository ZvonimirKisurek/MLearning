"""CLI:  python -m app.cli sync-sources | ingest [--dry-run] [--source SLUG ...]"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from app.config import get_settings
from app.ingestion.models import SourceState
from app.ingestion.sources import load_sources


def _dry_run(only: list[str] | None) -> int:
    """Fetch + parse every source without touching the DB or OpenAI. Doubles as a source-liveness check."""
    from app.ingestion.pipeline import fetch_all

    settings = get_settings()
    specs = [s for s in load_sources(settings.sources_file) if not only or s.slug in only]
    outcomes = asyncio.run(fetch_all(specs, {s.slug: SourceState() for s in specs}, settings))
    ok = failed = skipped = 0
    kinds: dict[str, int] = {}
    for o in outcomes:
        if o.skipped:
            skipped += 1
            print(f"SKIP  {o.spec.slug:24} {o.skipped}")
        elif o.error:
            failed += 1
            kinds[o.error_kind or "other"] = kinds.get(o.error_kind or "other", 0) + 1
            print(f"FAIL[{o.error_kind}] {o.spec.slug:24} {o.error[:120]}")
        else:
            ok += 1
            items = o.result.items
            print(f"OK    {o.spec.slug:24} {len(items):3} items  e.g. {items[0].title[:60] if items else '-'}")
    print(f"\n{ok} ok, {failed} failed, {skipped} skipped of {len(outcomes)}")
    if kinds:
        print("failures by kind:", ", ".join(f"{k}={v}" for k, v in sorted(kinds.items())))
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="mle-sprint")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sync-sources", help="upsert sources.yaml into the DB")
    ing = sub.add_parser("ingest", help="run the ingestion pipeline once")
    ing.add_argument("--dry-run", action="store_true", help="fetch+parse only; no DB, no embeddings")
    ing.add_argument("--source", action="append", help="limit to slug (repeatable)")
    lim = sub.add_parser("summarize", help="write AI summaries for recent articles that lack one")
    lim.add_argument("--limit", type=int)
    sub.add_parser("feed-stats", help="distribution of article-vs-skill similarity (calibrate MATCH_STRONG/MODERATE)")
    for name, help_ in (("generate-weekly", "generate next week's theme"), ("generate-daily", "generate today's briefing")):
        g = sub.add_parser(name, help=help_)
        g.add_argument("--force", action="store_true", help="regenerate even if one exists")
        g.add_argument("--dry-run", action="store_true", help="print the exact prompt; no LLM call, nothing stored")
        g.add_argument("--date", help="YYYY-MM-DD (default: auto)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if args.cmd == "sync-sources":
        from app.ingestion import repository

        specs = load_sources(get_settings().sources_file)
        print(f"synced {repository.upsert_sources(specs)} sources")
        return 0
    if args.cmd == "summarize":
        from app.curriculum.summaries import summarize_pending

        print(summarize_pending(limit=args.limit))
        return 0
    if args.cmd == "feed-stats":
        from app.db import get_pool

        with get_pool().connection() as conn:
            r = conn.execute(
                """select count(*) n, percentile_cont(array[0.1,0.25,0.5,0.75,0.9,0.99]) within group (order by sim) q from (
                     select max(1 - (a.embedding <=> k.embedding)) sim from articles a cross join skills k
                     where a.duplicate_of is null and a.embedding is not null and k.embedding is not null
                       and coalesce(a.published_at, a.fetched_at) > now() - interval '14 days' group by a.id) t""").fetchone()
        s = get_settings()
        print(f"articles: {r['n']}")
        if r["n"]:
            print("best-skill cosine similarity percentiles  p10 p25 p50 p75 p90 p99:", [round(x, 3) for x in r["q"]])
            print(f"current thresholds: strong>={s.match_strong}, moderate>={s.match_moderate}  "
                  "(suggest: strong ~ p90, moderate ~ p50)")
        return 0
    if args.cmd in ("generate-weekly", "generate-daily"):
        import json
        from datetime import date

        from app.curriculum import generators

        d = date.fromisoformat(args.date) if args.date else None
        if args.cmd == "generate-weekly":
            r = generators.generate_weekly_theme(week_start=d, force=args.force, dry_run=args.dry_run)
        else:
            r = generators.generate_daily_briefing(day=d, force=args.force, dry_run=args.dry_run)
        if args.dry_run:
            print(f"=== SYSTEM ===\n{r['system']}\n\n=== USER ({r['articles']} articles) ===\n{r['user']}")
        else:
            print(json.dumps(r, indent=2, default=str))
        return 0
    if args.dry_run:
        return _dry_run(args.source)
    from app.ingestion.pipeline import run_ingestion

    print(run_ingestion(trigger="manual", only=args.source))
    return 0


if __name__ == "__main__":
    sys.exit(main())
