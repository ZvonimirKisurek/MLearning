# MLE-Sprint

Personal AI/ML market-intelligence + curriculum dashboard. Ingests 130 sources every 6h, de-duplicates stories with pgvector, and (Phase 2+) turns the noise into a weekly theme and a daily mission targeted at my skill gaps.

## Architecture

```
sources.yaml ──► Celery beat (every 6h) ──► ingest_all
                                              │ 1. async fetch (robots.txt, UA, per-host throttle, backoff, ETag/304)
                                              │ 2. parse → RawItem (title, summary, url, date)
                                              │ 3. exact dedup: sha256(canonical URL)
                                              │ 4. embed (OpenAI text-embedding-3-small, batched, retried)
                                              │ 5. semantic dedup: pgvector HNSW cosine ≥ 0.92 within 14 days
                                              ▼
                                   Supabase Postgres (+pgvector)
                       sources · articles · ingestion_runs · skills · weekly_themes · daily_briefings
                                              ▲
                       FastAPI (Step 4) ◄──── Next.js dashboard (Step 5)
```

```
supabase/migrations/   SQL migrations (Supabase CLI compatible; also auto-applied by docker-compose)
backend/
  sources/sources.yaml   source catalogue (132 entries, 6 categories)
  app/config.py db.py    settings, psycopg pool (pgvector registered, pooler-safe)
  app/ingestion/         http.py parsers.py fetchers/ embeddings.py repository.py pipeline.py
  app/celery_app.py tasks.py cli.py main.py
  tests/
frontend/                Next.js app (Step 5)
```

## Roadmap
| Step | Scope | Status |
|---|---|---|
| 1 | Repo, schema, Supabase connection | done |
| 2 | Scrapers, parsers, embeddings, dedup, Celery beat | done (untested against live DB/feeds, see below) |
| 3 | Prompt engineering + weekly/daily generators, Pydantic output validation | next |
| 4 | FastAPI endpoints (`/briefing/today`, complete task, feed, skills) | |
| 5 | Next.js + shadcn/ui dashboard | |

## Run locally
```bash
cp .env.example .env            # add OPENAI_API_KEY and a real contact in USER_AGENT
docker compose up -d db redis   # pgvector Postgres + Redis; migrations auto-apply on first boot
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
pytest                                    # unit tests, no network/DB needed
python -m app.cli ingest --dry-run        # fetch+parse all sources, no DB/OpenAI; doubles as a liveness check
python -m app.cli ingest                  # full pipeline once
celery -A app.celery_app worker -l info & celery -A app.celery_app beat -l info
```
**Supabase:** `supabase link && supabase db push`, then set `DATABASE_URL` to the connection string (session pooler works; transaction pooler works too since prepared statements are disabled).

## Design notes
- **Politeness:** every request carries `USER_AGENT`; robots.txt is fetched per host and enforced (fails closed if unreachable/5xx, per RFC 9309); 1s min interval per host; 429/5xx → exponential backoff with jitter, honouring `Retry-After`; conditional GET (ETag/Last-Modified) → cheap 304s.
- **Official APIs only where robots blocks crawlers:** Reddit goes through OAuth (skipped without credentials); HN via Algolia; HF Daily Papers via its JSON API. X/Twitter has no free API, so researchers are tracked via blogs/Substacks.
- **Failure isolation:** one broken source never fails the run; per-source health + circuit breaker (5 failures → retry once per 24h).
- **Dedup:** URL hash first (free), embeddings second. Duplicates are stored with `duplicate_of` so they are never re-embedded and dedup quality is auditable. Tune `DEDUP_THRESHOLD` by inspecting `articles.duplicate_sim`.
- **Security:** RLS enabled with no policies on all tables; the browser never talks to Postgres directly, only the FastAPI backend does.

## Known caveats
- Feed URLs were written from memory and **not yet verified live** (my sandbox blocked egress). Run `ingest --dry-run`, then disable/fix dead entries in `sources.yaml`. The Anthropic feed is community-generated; The Batch and several newsletter URLs are the likeliest to need fixing.
- No scheduler lock: run a single `beat` instance. Ingestion is idempotent (`url_hash` unique), so overlapping runs are safe but wasteful.
