-- ─────────────────────────────────────────────────────────────────────────────
-- v_sensor_truth.is_anomaly tested for a value the source column FORBIDS.
--
-- FOUND BY THE AH16 WALK (2026-07-28, ASSET_HUB_DEEPWALK_EXPANSION_ROADMAP):
--
--   v_sensor_truth:                    (quality_flag = 'ANOMALY') AS is_anomaly
--   sensor_readings CHECK constraint:  quality_flag IS NULL OR quality_flag IN
--                                        ('good','uncertain','bad','stale')
--
-- 'ANOMALY' is not in that list. The database REJECTS the only value that would make
-- is_anomaly true, so the column has been false for all 77,814 readings and always would be.
-- This is not a fixture gap that a reseed fixes — it is dead by construction.
--
-- WHAT WAS BUILT ON TOP OF IT, all of it unreachable:
--   asset-hub.html   #sensor-anomaly-banner — added in Tier4.4 specifically to close the
--                    "anomaly buried in the per-parameter Z-score chip" gap. It never rendered
--                    once, so that gap stayed open the whole time: measured live on RC-001, the
--                    chip reads "ANOMALY 4.5σ" while the banner above it stays hidden.
--   index.html       Today's One Thing ranker (.eq('is_anomaly', true))
--   get_hive_dashboard  RPC — two migrations select ... WHERE is_anomaly = true
--   companion_source_registry.json  count_where is_anomaly
--   journey-home-fanout-parity.spec.ts  asserts on it, and passes, because 0 = 0
--
-- And formula_contracts.json z_score_anomaly_3sigma claims "edge fn: sensor-readings-ingest
-- sets quality_flag='ANOMALY' when |z|>3". That function does not mention quality_flag at all —
-- so the contract documented a rule nothing implemented, into a column that would have refused
-- it. Three layers each assuming another layer did the work.
--
-- THE FIX, AND WHY NOT JUST WIDEN THE CHECK. quality_flag is a DATA-QUALITY field with OPC-UA
-- semantics — is this reading trustworthy? An anomaly is a different claim entirely: the reading
-- is trustworthy AND the machine is behaving oddly. Folding 'ANOMALY' into that enum would make a
-- stale sensor and a failing bearing raise the same flag, and would silently reclassify every
-- anomalous reading as one of unknown quality. So the anomaly gets its own column, quality_flag
-- keeps its meaning, and the VIEW's column name and position are unchanged — every one of the
-- consumers above keeps working untouched and simply starts seeing true values.
-- ─────────────────────────────────────────────────────────────────────────────

-- 1. A dedicated flag. Non-volatile default, so PG11+ fills it in the catalog without
--    rewriting the 77k-row table.
ALTER TABLE public.sensor_readings
  ADD COLUMN IF NOT EXISTS is_anomaly boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.sensor_readings.is_anomaly IS
  'Machine-behaviour anomaly (|z| > 3 against the parameter''s rolling baseline), set by the '
  'sensor-readings-ingest edge fn. Distinct from quality_flag, which describes whether the '
  'reading itself is trustworthy — a good-quality reading can be anomalous, and a stale one '
  'usually is not. Registered as formula z_score_anomaly_3sigma.';

-- Consumers all filter is_anomaly = true within a recent window; anomalies are the rare case,
-- so a partial index keeps that lookup cheap without carrying the 99% that are false.
CREATE INDEX IF NOT EXISTS sensor_readings_anomaly_recent_idx
  ON public.sensor_readings (hive_id, asset_id, recorded_at DESC)
  WHERE is_anomaly;

-- 2. Re-create the view reading the real column.
--    Definition below is the CURRENT pg_get_viewdef with ONLY the is_anomaly expression changed:
--    same DISTINCT ON key, same column list, same order, same `id AS reading_id` alias. (A prior
--    step in this arc nearly dropped a DISTINCT ON and renamed a column by rewriting a view from
--    memory instead of from its dumped definition — this one was diffed against the dump.)
--    WITH (security_invoker = true) IS LOAD-BEARING AND MUST BE RESTATED. CREATE OR REPLACE VIEW
--    does not carry the existing reloptions forward — it CLEARS them. Dropping it here would make
--    the view run as its OWNER and bypass sensor_readings' RLS, turning a canonical read into a
--    cross-hive leak. Caught on this very migration: the first apply wiped it (pg_class.reloptions
--    went NULL) and it had to be restored. Verify after any future edit with
--      SELECT reloptions FROM pg_class WHERE relname = 'v_sensor_truth';
CREATE OR REPLACE VIEW public.v_sensor_truth
WITH (security_invoker = true) AS
SELECT DISTINCT ON (hive_id, asset_id, parameter)
  id AS reading_id,
  hive_id,
  asset_id,
  parameter,
  value,
  unit,
  quality_flag,
  recorded_at,
  source,
  is_anomaly
FROM public.sensor_readings s
ORDER BY hive_id, asset_id, parameter, recorded_at DESC;

COMMENT ON VIEW public.v_sensor_truth IS
  'Tier D canonical: latest sensor reading per (hive, asset, parameter) with is_anomaly shortcut. '
  'Closes the ops-home Today-ranker + asset-hub recent-sensor gap reads. Older history queryable '
  'via sensor_readings raw. 2026-07-28: is_anomaly now reads the sensor_readings.is_anomaly column; '
  'it previously tested quality_flag = ''ANOMALY'', a value the table CHECK forbids, so it could '
  'never be true.';
