-- Phase 3: AI summaries + indexes that back the feed API.
set search_path = public, extensions;

alter table public.articles add column ai_summary    text;
alter table public.articles add column ai_summary_at timestamptz;

-- Work queue for the summariser: "canonical articles that still need a summary".
create index articles_unsummarized_idx on public.articles (published_at desc)
  where duplicate_of is null and ai_summary is null;

-- Feed pagination is *keyset* (WHERE (ts, id) < (:last_ts, :last_id) ORDER BY ts DESC, id DESC): this
-- index lets Postgres jump to the cursor and read the next page without scanning/discarding earlier rows.
create index articles_feed_idx on public.articles ((coalesce(published_at, fetched_at)) desc, id desc)
  where duplicate_of is null;

-- "Also covered by N sources" looks up the duplicates of each canonical article.
create index articles_duplicate_of_idx on public.articles (duplicate_of) where duplicate_of is not null;
