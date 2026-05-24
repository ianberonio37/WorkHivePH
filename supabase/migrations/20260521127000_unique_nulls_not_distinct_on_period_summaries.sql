-- canonical_period_summaries: UNIQUE NULLS NOT DISTINCT (Postgres 15+)
-- =====================================================================
-- The original unique constraint `(hive_id, asset_tag, level, period_start)`
-- treated NULL as distinct (Postgres pre-15 default), so re-running the
-- hierarchical-summarizer backfill with `asset_tag IS NULL` (hive-wide
-- summaries) inserted duplicates instead of upserting. RAG flywheel turn 1
-- (see [[project-rag-flywheel-turn-1-2026-05-21]] finding #3) had to
-- manually dedupe stale zero-fail rows after the 5y backfill.
--
-- This migration switches to UNIQUE NULLS NOT DISTINCT so the constraint
-- treats NULL as a value: subsequent backfills upsert cleanly even when
-- asset_tag is NULL.
--
-- DROP + ADD is required (PG doesn't support ALTER CONSTRAINT for NULL
-- semantics). Pre-flight: dedupe any existing collisions so the new
-- constraint can be added without conflict.
--
-- Local: applies cleanly via `supabase migration up --local`.
-- Production: same SQL, no destructive data change beyond the dedupe.

BEGIN;

-- 1. Dedup any existing rows that the new tighter constraint would reject.
--    Keep the most recently generated row per logical key.
DELETE FROM public.canonical_period_summaries
WHERE id NOT IN (
  SELECT DISTINCT ON (hive_id, asset_tag, level, period_start) id
  FROM public.canonical_period_summaries
  ORDER BY hive_id, asset_tag, level, period_start, generated_at DESC NULLS LAST
);

-- 2. Drop the old constraint (whatever its auto-generated name is).
DO $$
DECLARE
  c_name text;
BEGIN
  SELECT con.conname INTO c_name
  FROM pg_constraint con
  JOIN pg_class    rel ON rel.oid = con.conrelid
  JOIN pg_namespace ns ON ns.oid = rel.relnamespace
  WHERE ns.nspname = 'public'
    AND rel.relname = 'canonical_period_summaries'
    AND con.contype = 'u'
    AND con.conname LIKE '%hive_id%level%';
  IF c_name IS NOT NULL THEN
    EXECUTE format('ALTER TABLE public.canonical_period_summaries DROP CONSTRAINT IF EXISTS %I', c_name);
  END IF;
END $$;

-- 3. Add the new constraint with NULLS NOT DISTINCT semantics.
ALTER TABLE public.canonical_period_summaries
  ADD CONSTRAINT canonical_period_summaries_unique_logical_key
  UNIQUE NULLS NOT DISTINCT (hive_id, asset_tag, level, period_start);

COMMIT;
