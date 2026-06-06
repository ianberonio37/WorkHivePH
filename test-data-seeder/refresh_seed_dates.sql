-- Non-destructive seed-date refresh (2026-06-06)
-- Shifts each EVENT table forward by its own interval so its newest row lands at ~now(),
-- repopulating time-windowed views (logbook team-feed 7d, closed-today, pm-done-today,
-- sensor-24h, alerts, amc-today) WITHOUT wiping the verified-correct dataset.
-- Deliberately EXCLUDES pm_assets + asset_risk_scores so the verified derived KPIs
-- (pm-overdue tile, risk-alerts tile) are preserved.
-- All timestamptz cols in a table shift by the same interval (preserves ordering);
-- alert tables anchor on detected_at so expires_at lands in the future (= active).
BEGIN;

-- logbook: date, closed_at, created_at, updated_at  (team-feed + closed-today)
UPDATE logbook SET
  date       = date       + iv,
  closed_at  = closed_at  + iv,
  created_at = created_at + iv,
  updated_at = updated_at + iv
FROM (SELECT now() - GREATEST(max(date), max(closed_at), max(created_at), max(updated_at)) AS iv FROM logbook) s;

-- pm_completions: completed_at  (pm-done-today)
UPDATE pm_completions SET
  completed_at = completed_at + iv
FROM (SELECT now() - max(completed_at) AS iv FROM pm_completions) s;

-- sensor_readings: recorded_at  (sensor-anomaly-24h card)
UPDATE sensor_readings SET
  recorded_at = recorded_at + iv
FROM (SELECT now() - max(recorded_at) AS iv FROM sensor_readings) s;

-- failure_signature_alerts: anchor detected_at -> expires_at goes future (active)
UPDATE failure_signature_alerts SET
  detected_at     = detected_at     + iv,
  acknowledged_at = acknowledged_at + iv,
  expires_at      = expires_at      + iv
FROM (SELECT now() - max(detected_at) AS iv FROM failure_signature_alerts) s;

-- anomaly_alerts: anchor created_at
UPDATE anomaly_alerts SET
  created_at       = created_at       + iv,
  detected_at      = detected_at      + iv,
  acknowledged_at  = acknowledged_at  + iv,
  suppressed_until = suppressed_until + iv
FROM (SELECT now() - GREATEST(max(created_at), max(detected_at)) AS iv FROM anomaly_alerts) s;

-- cross_hive_alerts: detected_at
UPDATE cross_hive_alerts SET
  detected_at = detected_at + iv
FROM (SELECT now() - max(detected_at) AS iv FROM cross_hive_alerts) s;

-- inventory_transactions: created_at  (recent inventory activity)
UPDATE inventory_transactions SET
  created_at = created_at + iv
FROM (SELECT now() - max(created_at) AS iv FROM inventory_transactions) s;

-- amc_briefings: shift_date is DATE -> integer-day shift; timestamptz cols share the day count
UPDATE amc_briefings SET
  shift_date   = shift_date   + n,
  generated_at = generated_at + (n || ' days')::interval,
  approved_at  = approved_at  + (n || ' days')::interval,
  expires_at   = expires_at   + (n || ' days')::interval
FROM (SELECT (CURRENT_DATE - max(shift_date)) AS n FROM amc_briefings) s;

-- shift_plans: shift_date DATE -> integer-day shift; timestamptz cols share the day count
UPDATE shift_plans SET
  shift_date   = shift_date   + n,
  created_at   = created_at   + (n || ' days')::interval,
  generated_at = generated_at + (n || ' days')::interval,
  published_at = published_at + (n || ' days')::interval,
  updated_at   = updated_at   + (n || ' days')::interval
FROM (SELECT (CURRENT_DATE - max(shift_date)) AS n FROM shift_plans) s;

COMMIT;

-- Verify: newest dates should now be ~today, nothing in the future
SELECT 'logbook.date'        AS k, max(date)::text        AS newest, (max(date)        > now())::text AS future FROM logbook
UNION ALL SELECT 'logbook.closed_at',  max(closed_at)::text,  (max(closed_at)  > now())::text FROM logbook
UNION ALL SELECT 'pm_completions',     max(completed_at)::text, (max(completed_at) > now())::text FROM pm_completions
UNION ALL SELECT 'sensor_readings',    max(recorded_at)::text, (max(recorded_at) > now())::text FROM sensor_readings
UNION ALL SELECT 'failure_sig_alerts', max(detected_at)::text, (max(detected_at) > now())::text FROM failure_signature_alerts
UNION ALL SELECT 'inventory_txns',     max(created_at)::text,  (max(created_at)  > now())::text FROM inventory_transactions
UNION ALL SELECT 'amc_briefings',      max(shift_date)::text,  (max(shift_date)::timestamptz > now())::text FROM amc_briefings;
