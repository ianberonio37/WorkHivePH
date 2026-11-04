-- a_machine_that_reports_is_not_an_anomaly: the anomaly composer's sensor source counts only the readings the ingest
-- flagged (is_anomaly, |z| > 3 against the reading's own baseline), and says when the newest one was; the home's
-- dashboard names the machine a flagged reading came from (migs 20261105000001 + 20261105000002). Found by the
-- group-journey walk GJ J17: 41 healthy vibration readings raised "Sensor readings drifting out of band" at score 100,
-- and the home's Today card said "vibration_mm_s flagged anomaly" without naming a machine.
-- Each leg runs the composer AS a member of the hive (authenticated + their claims) in its own BEGIN/ROLLBACK, so the
-- readings it inserts and the signals it writes go too.
-- Self-grounding: an approved machine of a hive with an active member, carrying no readings yet.
-- expect: fixture_found \| t
-- expect: healthy_readings_raise_no_sensor_score \| t
-- expect: flagged_readings_raise_the_sensor_score \| t
-- expect: the_signal_says_when \| t
-- expect: the_dashboard_names_the_machine \| t
CREATE TEMP TABLE _s AS
SELECT n.id AS node_id, n.name AS machine, n.hive_id,
       (SELECT hm.auth_uid FROM hive_members hm WHERE hm.hive_id = n.hive_id AND hm.status = 'active' AND hm.auth_uid IS NOT NULL
         ORDER BY hm.worker_name LIMIT 1) AS uid
  FROM asset_nodes n
 WHERE n.hive_id IS NOT NULL AND n.deleted_at IS NULL AND n.status = 'approved' AND n.name IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM sensor_readings s WHERE s.asset_id = n.id)
   AND (SELECT count(*) FROM asset_nodes o WHERE o.hive_id = n.hive_id AND o.name = n.name AND o.deleted_at IS NULL) = 1
   AND EXISTS (SELECT 1 FROM hive_members hm WHERE hm.hive_id = n.hive_id AND hm.status = 'active' AND hm.auth_uid IS NOT NULL)
 ORDER BY n.name
 LIMIT 1;
GRANT SELECT ON _s TO authenticated;
SELECT 'fixture_found | ' || EXISTS (SELECT 1 FROM _s WHERE uid IS NOT NULL);

BEGIN;
INSERT INTO sensor_readings (hive_id, asset_id, parameter, unit, value, recorded_at, source, is_anomaly)
SELECT hive_id, node_id, 'vibration_mm_s', 'mm/s', 2.0 + (g % 5) * 0.05, now() - (g * interval '2 minutes'), 'mqtt', false
  FROM _s, generate_series(1, 20) g;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT uid FROM _s)::text, 'role', 'authenticated')::text, true) IS NULL;
SET LOCAL ROLE authenticated;
SELECT compute_anomaly_signals((SELECT hive_id FROM _s)) >= 0;
RESET ROLE;
SELECT 'healthy_readings_raise_no_sensor_score | ' || NOT EXISTS (SELECT 1 FROM anomaly_signals a, _s
  WHERE a.hive_id = _s.hive_id AND a.machine = _s.machine AND a.sensor_zscore_score > 0);
ROLLBACK;

BEGIN;
INSERT INTO sensor_readings (hive_id, asset_id, parameter, unit, value, recorded_at, source, is_anomaly)
SELECT hive_id, node_id, 'vibration_mm_s', 'mm/s', CASE WHEN g <= 4 THEN 12.0 + g ELSE 2.0 END,
       now() - (g * interval '2 minutes'), 'mqtt', g <= 4
  FROM _s, generate_series(1, 20) g;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT uid FROM _s)::text, 'role', 'authenticated')::text, true) IS NULL;
SET LOCAL ROLE authenticated;
SELECT compute_anomaly_signals((SELECT hive_id FROM _s)) >= 0;
SELECT 'the_dashboard_names_the_machine | ' || ((get_hive_dashboard((SELECT hive_id FROM _s), now() - interval '12 hours')
  -> 'sensor_anomaly' ->> 'machine') = (SELECT machine FROM _s));
RESET ROLE;
SELECT 'flagged_readings_raise_the_sensor_score | ' || EXISTS (SELECT 1 FROM anomaly_signals a, _s
  WHERE a.hive_id = _s.hive_id AND a.machine = _s.machine AND a.sensor_zscore_score = 100
    AND (a.evidence -> 'sensor_zscore' ->> 'n_alerts')::int = 4);
SELECT 'the_signal_says_when | ' || EXISTS (SELECT 1 FROM anomaly_signals a, _s
  WHERE a.hive_id = _s.hive_id AND a.machine = _s.machine
    AND (a.evidence -> 'sensor_zscore' ->> 'last')::timestamptz > now() - interval '10 minutes');
ROLLBACK;
