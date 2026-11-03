-- Phase 9: per-chapter notebook. One free-text note per task, edited in place (auto-saved by the UI).
-- A column rather than a history table: the learner wants "my notes for this chapter", not an audit trail, and the
-- row is already addressed by task id, so reads/writes are single primary-key operations (fast enough to debounce-save).
set search_path = public, extensions;

alter table public.daily_tasks add column notes text not null default '' check (char_length(notes) <= 50000);
alter table public.daily_tasks add column notes_updated_at timestamptz;
