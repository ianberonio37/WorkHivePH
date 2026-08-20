-- v_sensor_recent DROPPED THE UNIT ITS ONLY READER SELECTS, SO THE WHOLE READ 400s.
--
-- Found 2026-08-20 by prove_field_names_survive during the stale->gate conversion arc: "1 field
-- name(s) no longer exist on their relation" — asset-hub selects `unit` from v_sensor_recent, and
-- the view does not have it.
--
-- This is not a cosmetic omission. PostgREST REJECTS an unknown column in select rather than
-- omitting it, so asset-hub's sensor telemetry read
--
--     .from('v_sensor_recent').select('parameter, value, unit, recorded_at, source')
--
-- returns 400 and the panel gets nothing at all. The unit is not missing from the data: sensor_readings
-- carries it, and v_sensor_truth already exposes it. Only this view drops it, while being the one
-- surface that asks for it — and `meta` is empty ({}), so there is no fallback path carrying it either.
--
-- A sensor reading rendered without its unit would ALSO fail the units_declared oracle in the same
-- breath: 47.3 of what is not a measurement. So the column is added rather than removed from the
-- caller. It is appended LAST rather than placed beside `value` where it belongs semantically:
-- CREATE OR REPLACE VIEW can only add columns at the end, and inserting mid-list is refused
-- ("cannot change name of view column"). Callers select by name, so position is immaterial to them.

CREATE OR REPLACE VIEW public.v_sensor_recent AS
 SELECT sr.id,
    sr.hive_id,
    sr.asset_id,
    sr.parameter,
    sr.value,
    sr.recorded_at,
    sr.source,
    sr.meta,
    n.tag AS asset_tag,
    n.name AS asset_name,
    n.iso_class,
    sr.unit
   FROM sensor_readings sr
     LEFT JOIN asset_nodes n ON n.id = sr.asset_id
  WHERE sr.recorded_at >= (now() - '30 days'::interval);

-- ★RE-APPLY security_invoker. CREATE OR REPLACE VIEW does NOT carry a view's reloptions forward, and
-- 20260621000001_views_security_invoker_generalize.sql set this one deliberately: v_sensor_recent
-- filters sensor_readings on recorded_at ALONE, so without security_invoker it runs as the view
-- OWNER and the underlying RLS is never evaluated for the caller -- every hive's sensor data through
-- one time-windowed view. Measured by validate_db_adoption.py as D4 falling 58 -> 57.
ALTER VIEW public.v_sensor_recent SET (security_invoker = on);
