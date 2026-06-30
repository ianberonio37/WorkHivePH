-- Fix: benchmark-compute's computeNetwork upsert silently failed forever, so the
-- cross-hive benchmark network (intelligence-api ?endpoint=benchmarks, the
-- ph-intelligence page, hive.html) NEVER populated.
--
-- Root cause: network_benchmarks' unique index was an EXPRESSION index on
-- (equipment_category, COALESCE(industry, '')). PostgREST's on_conflict can only
-- target plain columns, so the upsert errored with `column "COALESCE" does not
-- exist` (HTTP 400) — and because computeNetwork never checked the upsert's
-- {error}, the failure was swallowed and the function still returned 200.
--
-- Fix: make `industry` NOT NULL DEFAULT '' and replace the expression index with a
-- plain composite UNIQUE constraint, so `on_conflict=equipment_category,industry`
-- resolves cleanly. (industry has always been written as NULL/'' — no real data
-- groups by it yet — so the backfill is a no-op-to-'' and reads are unaffected:
-- intelligence-api only filters industry when a non-empty ?industry param is given.)
UPDATE network_benchmarks SET industry = '' WHERE industry IS NULL;
ALTER TABLE network_benchmarks ALTER COLUMN industry SET DEFAULT '';
ALTER TABLE network_benchmarks ALTER COLUMN industry SET NOT NULL;
DROP INDEX IF EXISTS idx_network_benchmarks_unique;
ALTER TABLE network_benchmarks
  ADD CONSTRAINT network_benchmarks_cat_industry_key UNIQUE (equipment_category, industry);
