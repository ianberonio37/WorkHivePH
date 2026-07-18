-- 20260712000017_schedule_items_source_ref.sql
-- Dayplanner/Growth PDDA arc (2026-07-12) — Ext-5 spine keystone K2: ground dayplanner tasks.
--
-- Before this, schedule_items were FREE-TEXT (title/date/times/category/notes only) — a dayplanner
-- task could not TRACE to the intelligence that motivated it (a PM due, a risk asset, a shift-plan
-- row, an alert), so the dayplanner was an ISLAND and index.html falsely claimed it "Pulls from PM
-- schedule". These two nullable columns let a task carry its PROVENANCE, so "plan my day from the
-- risk/PMs/shift-plan" becomes a grounded compose-FROM instead of retyped strings.
--   source_kind — where the task came from: 'pm' | 'risk' | 'alert' | 'shift' | 'logbook' | 'manual'
--   source_ref  — the source's id/tag (pm scope_item_id, asset_tag, alert dedupeKey, shift_plan id, …)
-- No RLS change: schedule_items_read/_write are auth_uid-scoped (own rows) and cover the new columns.
-- Idempotent (ADD COLUMN IF NOT EXISTS). Existing rows keep NULL (manual free-text tasks, unchanged).

ALTER TABLE public.schedule_items
  ADD COLUMN IF NOT EXISTS source_kind text,
  ADD COLUMN IF NOT EXISTS source_ref  text;

COMMENT ON COLUMN public.schedule_items.source_kind IS
  'Provenance of the task: pm | risk | alert | shift | logbook | manual (NULL = legacy free-text).';
COMMENT ON COLUMN public.schedule_items.source_ref IS
  'Id/tag of the source that motivated the task (pm scope_item_id, asset_tag, shift_plan id, …).';
