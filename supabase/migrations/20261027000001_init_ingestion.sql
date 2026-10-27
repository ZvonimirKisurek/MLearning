-- MLE-Sprint: ingestion schema.
-- Works on Supabase and on plain pgvector Postgres (docker-compose).

create schema if not exists extensions;
create extension if not exists vector with schema extensions;
set search_path = public, extensions;

-- ---------------------------------------------------------------------------
-- sources: one row per feed/API/scraper target. YAML (backend/sources/sources.yaml)
-- is the source of truth for definition; this table also holds runtime health state.
-- ---------------------------------------------------------------------------
create table public.sources (
  id                   uuid primary key default gen_random_uuid(),
  slug                 text not null unique,
  name                 text not null,
  category             text not null check (category in
                         ('research','industry_news','engineering_blog','community','newsletter','researcher')),
  kind                 text not null check (kind in
                         ('rss','hackernews','reddit','github_trending','hf_daily_papers')),
  url                  text not null,
  config               jsonb not null default '{}',
  weight               real not null default 1.0,      -- prior on source quality, used in relevance ranking (Phase 2)
  enabled              boolean not null default true,
  -- HTTP conditional-GET validators: lets us get a cheap 304 instead of re-downloading unchanged feeds.
  etag                 text,
  last_modified        text,
  -- health tracking / circuit breaker
  last_fetched_at      timestamptz,
  last_success_at      timestamptz,
  last_error           text,
  consecutive_failures int not null default 0,
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- articles: every fetched item. Duplicates are KEPT (duplicate_of set) so that
-- (a) we never re-embed/re-evaluate the same URL, and (b) we can audit dedup quality.
-- ---------------------------------------------------------------------------
create table public.articles (
  id               uuid primary key default gen_random_uuid(),
  source_id        uuid not null references public.sources(id) on delete cascade,
  url              text not null,                 -- canonicalised (tracking params stripped)
  url_hash         text not null unique,          -- sha256(url): exact-dedup key, avoids paying for embeddings twice
  title            text not null,
  summary          text,
  author           text,
  published_at     timestamptz,
  fetched_at       timestamptz not null default now(),
  -- Embedding of "title + summary". 1536 dims = OpenAI text-embedding-3-small.
  -- Cosine distance (<=>) is used: it compares direction, not magnitude, which is what
  -- we want for "do these two texts talk about the same thing".
  embedding        vector(1536),
  duplicate_of     uuid references public.articles(id) on delete set null,
  duplicate_sim    real,                          -- cosine similarity to the canonical article
  engagement       int,                           -- HN points / HF upvotes / stars today, when available
  relevance_score  real,                          -- filled by Phase 2
  tags             text[] not null default '{}',
  metadata         jsonb not null default '{}'
);

create index articles_published_idx on public.articles (published_at desc) where duplicate_of is null;
create index articles_source_idx    on public.articles (source_id);
-- HNSW = approximate nearest-neighbour graph index. Partial: only canonical (non-duplicate)
-- articles are candidates for "have we seen this story?" lookups.
create index articles_embedding_hnsw on public.articles
  using hnsw (embedding vector_cosine_ops) where duplicate_of is null;

-- ---------------------------------------------------------------------------
create table public.ingestion_runs (
  id          uuid primary key default gen_random_uuid(),
  trigger     text not null default 'manual',     -- 'beat' | 'manual'
  started_at  timestamptz not null default now(),
  finished_at timestamptz,
  status      text not null default 'running' check (status in ('running','success','partial','failed')),
  stats       jsonb not null default '{}'
);

-- Security: the backend connects with a privileged role (bypasses RLS). The browser must
-- never read these tables directly with the anon key -> RLS on, zero policies = deny all.
alter table public.sources        enable row level security;
alter table public.articles       enable row level security;
alter table public.ingestion_runs enable row level security;
