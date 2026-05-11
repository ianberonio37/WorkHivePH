-- Logbook updated_at -- closes PRODUCTION_FIXES #43 L2
--
-- logbook is a multi-worker content table (notes / action / problem)
-- but had no `updated_at` column, so optimistic-concurrency couldn't
-- be implemented at all. This migration adds the column + a trigger
-- that auto-bumps it on every UPDATE so consumers can use the
-- `.eq('updated_at', oldStamp)` OC pattern.

ALTER TABLE public.logbook
  ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

-- Auto-bump trigger. Reuses the SECURITY DEFINER + search_path lockdown
-- pattern established in PRODUCTION_FIXES #50.

CREATE OR REPLACE FUNCTION public.touch_updated_at()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_logbook_touch_updated_at ON public.logbook;
CREATE TRIGGER trg_logbook_touch_updated_at
  BEFORE UPDATE ON public.logbook
  FOR EACH ROW EXECUTE FUNCTION public.touch_updated_at();

-- Backfill existing rows so the column is populated for old data too.
-- New inserts get DEFAULT now() automatically; existing rows would be
-- NULL without this UPDATE.
UPDATE public.logbook SET updated_at = COALESCE(created_at, now()) WHERE updated_at IS NULL OR updated_at = '1970-01-01'::timestamptz;
