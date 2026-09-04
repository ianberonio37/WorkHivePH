-- canonical_period_summaries.source_row_ids: uuid[] -> text[], to match the key its sources use.
--
-- MEASURED 2026-08-27 (T90). The column's own comment says "traceability back to logbook rows", and
-- hierarchical-summarizer does write it (index.ts :346) — but it filters to UUID-shaped ids first
-- (:334-335), guarded by a comment claiming "Production logbook IDs (gen_random_uuid()) always pass
-- this filter." That premise is false everywhere, not just locally:
--
--   * the baseline migration declares logbook.id as "text" NOT NULL with NO uuid default
--     (20260420000000_baseline.sql :874),
--   * logbook.html writes id: Date.now().toString() (:4958) — a millisecond timestamp string,
--   * and the prod schema dump carries the same "source_row_ids" "uuid"[].
--
-- So every logbook id failed the filter, validSourceIds was always [], and the column has been empty
-- in production as well as locally: 2 rows exist, 0 carry a source id. A uuid[] column whose only
-- source table is keyed by text could never have been filled — the two ends were never able to meet.
--
-- Widening is the small end of the fork. The alternative — re-keying logbook to uuid — touches every
-- attribution join that reads logbook.id as text (pm_completions, xp ledgers, embeddings), which is a
-- far larger change to buy the same traceability.
--
-- SAFE BY CONSTRUCTION: the column is empty in every environment, so the USING cast moves no data.
-- IDEMPOTENT: guarded on the current type, so re-running is a no-op.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name   = 'canonical_period_summaries'
      AND column_name  = 'source_row_ids'
      AND udt_name     = '_uuid'
  ) THEN
    ALTER TABLE public.canonical_period_summaries
      ALTER COLUMN source_row_ids TYPE text[] USING source_row_ids::text[];
  END IF;
END $$;

COMMENT ON COLUMN public.canonical_period_summaries.source_row_ids IS
  'Traceability back to the rows this digest summarises. text[] because logbook.id is text '
  '(client-generated, not a uuid) — a uuid[] here could never hold a logbook key.';
