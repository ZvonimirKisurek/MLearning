-- Phase 6: ledger of every LLM call, used for the in-app daily spending cap and `cli usage`.
set search_path = public, extensions;

create table public.llm_usage (
  id            bigserial primary key,
  at            timestamptz not null default now(),
  purpose       text not null,          -- WeeklyThemeOutput | DailyBriefingOutput | SummaryBatch
  model         text not null,
  input_tokens  int  not null,
  output_tokens int  not null,          -- includes the model's thinking tokens (they are billed as output)
  cost_usd      numeric(10,5) not null  -- our estimate from the price table in app/curriculum/usage.py
);
create index llm_usage_at_idx on public.llm_usage (at desc);
alter table public.llm_usage enable row level security;
