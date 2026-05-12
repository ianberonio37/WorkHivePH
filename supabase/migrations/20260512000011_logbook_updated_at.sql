-- logbook.updated_at + auto-touch trigger (precondition for OC adoption).
--
-- PRODUCTION_FIXES #43 calls out logbook as the highest-stakes table
-- without optimistic concurrency: 5 writer files, multi-worker note
-- races possible. Adoption needs an `updated_at` column the UI can read
-- + send back as a guard. The column doesn't exist today; this migration
-- adds it.
--
-- Strategy:
--   1. Add `updated_at timestamptz NOT NULL DEFAULT now()`.
--   2. Backfill existing rows: copy from closed_at when present, else
--      created_at, else now(). Avoids a wave of NULLs.
--   3. Create a BEFORE UPDATE trigger that bumps updated_at on every
--      column change. Writers don't need to set the field themselves;
--      readers send the read-time value back as the .eq('updated_at',
--      ...) OC guard.
--   4. SECURITY DEFINER + locked search_path so cron / edge fns can
--      trigger updates without subverting the touch.
--
-- After this lands the logbook.html saveEdit path can adopt the canonical
-- OC pattern (read updated_at, write with .eq guard, retry on conflict).
--
-- Skills consulted: architect (OC pattern, invariant by trigger),
-- data-engineer (NULL-safe backfill, default value), maintenance-expert
-- (multi-worker logbook race is a real plant-floor scenario).

BEGIN;

-- ── 1. Add the column ───────────────────────────────────────────────────────

ALTER TABLE public.logbook
  ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

COMMENT ON COLUMN public.logbook.updated_at IS
  'Auto-touched by trg_logbook_touch_updated_at on every UPDATE. Sent back to writers as the optimistic-concurrency guard (.eq(updated_at, oldStamp)).';

-- ── 2. Backfill from closed_at / created_at ─────────────────────────────────
-- Existing rows defaulted to now() above; rewrite with the best historical
-- approximation so reports that depend on this column show sensible dates.

UPDATE public.logbook
SET updated_at = COALESCE(closed_at, created_at, now())
WHERE updated_at IS NOT NULL;

-- ── 3. Touch trigger ────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.touch_logbook_updated_at()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_catalog
AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END
$$;

COMMENT ON FUNCTION public.touch_logbook_updated_at() IS
  'BEFORE UPDATE on logbook: bumps updated_at to now(). Paired with the optimistic-concurrency guard in writer pages.';

DROP TRIGGER IF EXISTS trg_logbook_touch_updated_at ON public.logbook;

CREATE TRIGGER trg_logbook_touch_updated_at
BEFORE UPDATE ON public.logbook
FOR EACH ROW
EXECUTE FUNCTION public.touch_logbook_updated_at();

-- ── 4. Index ────────────────────────────────────────────────────────────────
-- Optimistic concurrency reads always include updated_at; lightweight
-- B-tree index keeps the .eq lookup fast even as the table grows.

CREATE INDEX IF NOT EXISTS idx_logbook_updated_at
  ON public.logbook (updated_at);

-- ── 5. Audit row ────────────────────────────────────────────────────────────

DO $$
DECLARE
  cnt bigint;
BEGIN
  SELECT count(*) INTO cnt FROM public.logbook;
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'automation_log') THEN
    INSERT INTO public.automation_log (job_name, status, detail)
    VALUES (
      'logbook_updated_at_added',
      'success',
      format('Added updated_at column + trigger to logbook (%s rows backfilled).', cnt)
    );
  END IF;
END
$$;

COMMIT;
