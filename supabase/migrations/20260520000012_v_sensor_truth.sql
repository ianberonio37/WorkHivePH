-- v_sensor_truth — canonical wrapper for the most recent sensor reading
-- per (hive, asset, parameter). Surfaces both the live value and the
-- anomaly flag.
--
-- Closes 2 gap reads identified by audit_calm_dashboard_canonical
-- (ops-home Today's One Thing sensor anomaly probe; asset-hub recent
-- sensor card).
--
-- Contract:
--   reading_id       latest reading UUID
--   hive_id          scope
--   asset_id         asset_nodes.id (uuid)
--   parameter        sensor parameter ('vibration_rms_g', 'temp_c', etc.)
--   value            most recent numeric value
--   unit             sensor unit
--   quality_flag     'OK'|'STALE'|'ANOMALY' (matches anomaly_baseline contract)
--   recorded_at      timestamp of the reading
--   source           ingestion source ('mqtt'|'opcua'|'manual'|...)
--   is_anomaly       boolean shortcut for the ANOMALY flag
--
-- The DISTINCT ON pattern returns ONE row per (hive,asset,parameter) —
-- the most recent. Older readings still queryable via sensor_readings raw.

BEGIN;

CREATE OR REPLACE VIEW public.v_sensor_truth AS
SELECT DISTINCT ON (s.hive_id, s.asset_id, s.parameter)
  s.id                                            AS reading_id,
  s.hive_id,
  s.asset_id,
  s.parameter,
  s.value,
  s.unit,
  s.quality_flag,
  s.recorded_at,
  s.source,
  (s.quality_flag = 'ANOMALY')                    AS is_anomaly
FROM public.sensor_readings s
ORDER BY s.hive_id, s.asset_id, s.parameter, s.recorded_at DESC;

COMMENT ON VIEW public.v_sensor_truth IS
  'Tier D canonical: latest sensor reading per (hive, asset, parameter) with is_anomaly shortcut. Closes the ops-home Today-ranker + asset-hub recent-sensor gap reads. Older history queryable via sensor_readings raw.';

GRANT SELECT ON public.v_sensor_truth TO anon, authenticated;

INSERT INTO public.canonical_sources (domain, source_kind, source_name, owner_skill, freshness, contract, description, registered_at)
VALUES (
  'sensor_truth',
  'view',
  'v_sensor_truth',
  'realtime-engineer',
  'realtime',
  '{"columns":["reading_id","hive_id","asset_id","parameter","value","unit","quality_flag","recorded_at","source","is_anomaly"]}'::jsonb,
  'Latest-per-(hive,asset,parameter) sensor reading. Closes 2 gap reads on ops-home + asset-hub.',
  now()
)
ON CONFLICT (domain) DO UPDATE
  SET source_name = EXCLUDED.source_name,
      contract    = EXCLUDED.contract,
      description = EXCLUDED.description;

COMMIT;
