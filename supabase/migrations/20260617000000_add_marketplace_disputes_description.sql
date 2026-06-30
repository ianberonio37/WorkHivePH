-- §13 P-fully sweep (2026-06-17) caught a data-loss bug: marketplace.html handleSubmitDispute
-- REQUIRES dispute-description (validates min 20 chars) but the marketplace_disputes INSERT
-- omitted it entirely — the table had no column for it, so the buyer's detailed dispute text
-- was silently discarded (only the `reason` dropdown persisted). Add the column so the
-- description is stored; the page insert is updated to carry `description: desc`.
alter table public.marketplace_disputes
  add column if not exists description text;

comment on column public.marketplace_disputes.description is
  'Buyer''s free-text dispute description (required min-20 chars in the UI). Added 2026-06-17 — was previously captured + validated but dropped on insert.';
