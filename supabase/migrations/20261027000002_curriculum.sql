-- MLE-Sprint: curriculum / briefing tables (used from Phase 2; created now so the schema is stable).
set search_path = public, extensions;

create table public.skills (
  id          uuid primary key default gen_random_uuid(),
  slug        text not null unique,
  name        text not null,
  level       int  not null default 0 check (level between 0 and 100),   -- current self-assessed proficiency
  target      int  not null default 80 check (target between 0 and 100),
  updated_at  timestamptz not null default now()
);

create table public.skill_history (
  id          bigserial primary key,
  skill_id    uuid not null references public.skills(id) on delete cascade,
  level       int  not null,
  recorded_at timestamptz not null default now()
);

create table public.weekly_themes (
  id            uuid primary key default gen_random_uuid(),
  week_start    date not null unique,             -- Monday of the ISO week
  title         text not null,
  rationale     text,
  target_skills text[] not null default '{}',     -- skills.slug values
  payload       jsonb not null,                   -- full LLM output (validated by Pydantic before insert)
  created_at    timestamptz not null default now()
);

create table public.daily_briefings (
  id            uuid primary key default gen_random_uuid(),
  day           date not null unique,
  theme_id      uuid references public.weekly_themes(id) on delete set null,
  payload       jsonb not null,                   -- {morning_reading, hands_on_task, market_insight}
  completed_at  timestamptz,                      -- null = not done
  created_at    timestamptz not null default now()
);

alter table public.skills          enable row level security;
alter table public.skill_history   enable row level security;
alter table public.weekly_themes   enable row level security;
alter table public.daily_briefings enable row level security;

insert into public.skills (slug, name, level, target) values
  ('pytorch',        'PyTorch',                     20, 80),
  ('classical-ml',   'Classical ML & Math',         30, 75),
  ('rag',            'RAG Architectures',           25, 85),
  ('vector-db',      'Vector Databases',            35, 80),
  ('llm-finetuning', 'LLM Fine-tuning',             10, 75),
  ('mlops',          'MLOps & Model Deployment',    30, 80),
  ('llm-evals',      'LLM Evaluation',              15, 70)
on conflict (slug) do nothing;
