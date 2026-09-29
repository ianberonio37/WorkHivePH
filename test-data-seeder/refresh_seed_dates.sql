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
--
-- ★PER HIVE, NOT PER TABLE (2026-09-18, W45972). This was one interval for the whole table, anchored on
-- the single newest row anywhere in it. That refreshes the ONE hive that happened to be newest and
-- leaves every other hive exactly as stale as it was relative to that lane. Measured before this change,
-- after a successful whole-table refresh: Dela Cruz Delivery Fleet 7 entries in the last 7 days, and
-- Baguio / Lucena / Manila - the three PLANT hives, the only ones with the members, assets and PM
-- templates to climb the Maturity Stairway - sat at 0 entries in 30 days, newest row 44 days old.
-- So compute_hive_readiness() pinned all three at Stair 1 on "0 of 5 active workers writing entries this
-- week", and PH Intelligence, which gates at Stair 3, was unreachable for every seeded persona. A table
-- is not the unit a tenant experiences; a hive is. Shifting per hive preserves each hive's internal
-- ordering - the thing a timeline needs - while restoring recency for all of them. Rows with no hive
-- (the solo lane) are left alone: they belong to no tenant's window.
UPDATE logbook l SET
  date       = l.date       + s.iv,
  closed_at  = l.closed_at  + s.iv,
  created_at = l.created_at + s.iv,
  updated_at = l.updated_at + s.iv
FROM (
  -- ★AND THE ANCHOR MUST NOT INCLUDE A COLUMN THIS WRITE ITSELF SETS (2026-09-18, same row). The anchor
  -- was GREATEST(max(date), max(closed_at), max(created_at), max(updated_at)) - and logbook carries a
  -- row-touch trigger, so the instant this UPDATE runs, updated_at becomes now(). On every run after the
  -- first, GREATEST() therefore returns now(), iv evaluates to zero, and the refresh silently does
  -- NOTHING while reporting success - its verify block reads max(closed_at), which the first run had
  -- already moved. Measured: all six hives showed max_updated = now() and three of them still had their
  -- newest EVENT 44 days old. A refresh that anchors on a column its own write updates can only ever
  -- work once, and nothing in its output says so. The anchor is now the three columns that describe
  -- when the work HAPPENED; updated_at is bookkeeping and rides along.
  SELECT hive_id,
         now() - GREATEST(max(date), max(closed_at), max(created_at)) AS iv
    FROM logbook WHERE hive_id IS NOT NULL GROUP BY hive_id
) s
WHERE l.hive_id = s.hive_id;

-- pm_completions: completed_at  (pm-done-today)
-- WHOLE-DAY shift, unlike every other table here: pm_completions_dedup_uidx is unique on
-- (scope_item_id, worker_name, (completed_at AT TIME ZONE 'UTC')::date). A fractional shift moves rows
-- across UTC-date boundaries unevenly and collapses adjacent-date completions onto one date — the
-- refresh aborted on exactly that collision on 2026-08-21. A whole-day shift maps every UTC date 1:1,
-- so rows that were unique stay unique. The day count lands the newest row TODAY if its time-of-day
-- has already passed, else YESTERDAY — never in the future, because a completion stamped later than
-- now() is manufactured freshness.
-- ...and in TWO PHASES, because the index is NON-DEFERRABLE: even a uniform shift collides
-- TRANSIENTLY mid-UPDATE when a shifted row lands on a date an unshifted sibling still occupies
-- (measured 2026-08-21: key 2026-07-17 collided with a not-yet-shifted row). Phase 1 jumps every row
-- +400000 days plus the real shift (~year 3121 — a date space no unshifted row occupies); phase 2
-- uniformly removes the jump. Day arithmetic is exact (no year/leap clamping), so the round trip is
-- lossless and the final dates equal a single nd-day shift.
-- ★AND IT MUST SKIP THE HIVE-LESS ROWS UNTIL A MIGRATION LANDS (2026-09-18, W45972). Shifting
-- completed_at fires audit_pm_completion_amendment(), which writes NEW.hive_id into hive_audit_log -
-- a NOT NULL column - so a SOLO worker's completion aborts the whole refresh with a raw constraint
-- violation. That is a real product defect, not a seeder problem: it means a hive-less worker can
-- never amend a PM completion at all. supabase/migrations/20260918000001_a_solo_worker_could_never_
-- amend_a_pm_completion.sql returns the trigger early for a hive-less row; it is NOT applied, because
-- migrations are Ian's gate. Until then these rows keep their dates, which costs nothing here: a
-- hive-less completion feeds no hive's PM compliance, so no readiness axis reads it. Measured: 1 row
-- of 1,613, whose pm_asset and pm_scope_item are hive-less too.
UPDATE pm_completions SET
  completed_at = completed_at + make_interval(days => 400000 + s.nd)
FROM (
  SELECT (current_date - (max(completed_at AT TIME ZONE 'UTC'))::date)
         - CASE WHEN (max(completed_at AT TIME ZONE 'UTC'))::time > (now() AT TIME ZONE 'UTC')::time
                THEN 1 ELSE 0 END AS nd
  FROM pm_completions WHERE hive_id IS NOT NULL
) s
WHERE pm_completions.hive_id IS NOT NULL;
UPDATE pm_completions SET
  completed_at = completed_at - make_interval(days => 400000)
WHERE hive_id IS NOT NULL;

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

-- ★THE TWO TABLES THE READINESS MODEL READS AND THIS REFRESH DID NOT SHIFT (2026-09-18, W45972).
-- compute_hive_readiness() decides every hive's Maturity Stair from five axes, and TWO of them are fed
-- by tables that were never in this file - so those axes could not recover from seed drift no matter how
-- often the refresh ran. LEADERSHIP is supervisor_actions_7d, counted from hive_audit_log where action is
-- approve/reject/kick/assign/verify; RESILIENCE is voice_journal_30d. Both windows had emptied, so every
-- hive on the platform was pinned at Stair 0-1 with the honest-looking blocker "0 of 5 active workers
-- writing entries this week" - and PH Intelligence, which gates at Stair 3, could not be reached by ANY
-- seeded persona. Four ph_intelligence_reports rows sat behind a door no cast could open, so no design
-- lens had ever seen the page's real content; the locked panel was the whole of the evidence.
-- A refresh that describes the tables it happened to know about is the same shape as a glob that
-- describes where you looked rather than where the thing lives.
-- Both are hive-scoped, so both shift PER HIVE for the reason given on logbook above.
UPDATE hive_audit_log a SET
  created_at = a.created_at + s.iv
FROM (SELECT hive_id, now() - max(created_at) AS iv
        FROM hive_audit_log WHERE hive_id IS NOT NULL GROUP BY hive_id) s
WHERE a.hive_id = s.hive_id;

UPDATE voice_journal_entries v SET
  created_at = v.created_at + s.iv
FROM (SELECT hive_id, now() - max(created_at) AS iv
        FROM voice_journal_entries WHERE hive_id IS NOT NULL GROUP BY hive_id) s
WHERE v.hive_id = s.hive_id;

COMMIT;

-- Verify: newest dates should now be ~today, nothing in the future
SELECT 'logbook.date'        AS k, max(date)::text        AS newest, (max(date)        > now())::text AS future FROM logbook
UNION ALL SELECT 'logbook.closed_at',  max(closed_at)::text,  (max(closed_at)  > now())::text FROM logbook
UNION ALL SELECT 'pm_completions',     max(completed_at)::text, (max(completed_at) > now())::text FROM pm_completions
UNION ALL SELECT 'sensor_readings',    max(recorded_at)::text, (max(recorded_at) > now())::text FROM sensor_readings
UNION ALL SELECT 'failure_sig_alerts', max(detected_at)::text, (max(detected_at) > now())::text FROM failure_signature_alerts
UNION ALL SELECT 'inventory_txns',     max(created_at)::text,  (max(created_at)  > now())::text FROM inventory_transactions
UNION ALL SELECT 'amc_briefings',      max(shift_date)::text,  (max(shift_date)::timestamptz > now())::text FROM amc_briefings
UNION ALL SELECT 'hive_audit_log',     max(created_at)::text,  (max(created_at)  > now())::text FROM hive_audit_log
UNION ALL SELECT 'voice_journal',      max(created_at)::text,  (max(created_at)  > now())::text FROM voice_journal_entries;
