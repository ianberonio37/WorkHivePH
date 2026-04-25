-- Analytics Indexes + Cache Table
-- Speeds up HiveBoard MTBF, MTTR, and downtime queries as logbook grows.
-- Cache stores pre-computed per-machine analytics so the board doesn't
-- re-scan 90 days of logbook on every page load.

-- ── INDEXES ──────────────────────────────────────────────────────────────────

-- General hive + date range queries (loadAnalytics, loadFeed, loadMtbf, loadMttr)
CREATE INDEX IF NOT EXISTS idx_logbook_hive_date
  ON logbook (hive_id, created_at DESC);

-- Breakdown-specific queries (loadMtbf, loadMttr, loadDowntime)
CREATE INDEX IF NOT EXISTS idx_logbook_hive_type
  ON logbook (hive_id, maintenance_type);

-- Closed breakdown queries for MTTR (status + maintenance_type + closed_at)
CREATE INDEX IF NOT EXISTS idx_logbook_hive_type_status
  ON logbook (hive_id, maintenance_type, status, closed_at DESC);


-- ── CACHE TABLE ───────────────────────────────────────────────────────────────

-- Stores nightly pre-computed analytics per hive.
-- mtbf_by_machine and mttr_by_machine are JSONB arrays so the board can
-- render the full per-machine detail view directly from cache.
CREATE TABLE IF NOT EXISTS hive_analytics_cache (
  hive_id           uuid REFERENCES hives(id) ON DELETE CASCADE PRIMARY KEY,
  mtbf_by_machine   jsonb,   -- [{machine, avgDays, count}]
  mttr_by_machine   jsonb,   -- [{machine, avgMs, count}]
  computed_at       timestamptz DEFAULT now() NOT NULL
);


-- ── PG_CRON JOB ──────────────────────────────────────────────────────────────
-- Requires the pg_cron extension enabled in Supabase (Database > Extensions).
-- Runs nightly at 02:00 UTC. Recomputes MTBF + MTTR for every active hive
-- and upserts one row per hive into hive_analytics_cache.
--
-- NOTE: Only run the cron block below AFTER enabling pg_cron in
-- Supabase Dashboard > Database > Extensions > pg_cron.
-- The CREATE TABLE above is safe to run immediately without pg_cron.

/*
SELECT cron.schedule(
  'nightly-analytics-cache',   -- unique job name
  '0 2 * * *',                 -- every day at 02:00 UTC
  $$
  INSERT INTO hive_analytics_cache (hive_id, mtbf_by_machine, mttr_by_machine, computed_at)
  SELECT
    h.id AS hive_id,

    -- MTBF: group breakdown events per machine, compute avg gap between failures
    (
      SELECT jsonb_agg(row_to_json(m))
      FROM (
        SELECT
          machine,
          ROUND(
            EXTRACT(EPOCH FROM (MAX(created_at) - MIN(created_at))) /
            NULLIF(COUNT(*) - 1, 0) / 86400.0,
            2
          ) AS "avgDays",
          COUNT(*) AS count
        FROM logbook
        WHERE hive_id = h.id
          AND maintenance_type = 'Breakdown / Corrective'
          AND machine IS NOT NULL AND machine <> ''
          AND created_at >= NOW() - INTERVAL '90 days'
        GROUP BY machine
        HAVING COUNT(*) >= 2
        ORDER BY "avgDays" ASC
      ) m
    ) AS mtbf_by_machine,

    -- MTTR: group closed breakdown jobs per machine, compute avg repair time
    (
      SELECT jsonb_agg(row_to_json(r))
      FROM (
        SELECT
          machine,
          ROUND(
            AVG(
              CASE
                WHEN downtime_hours IS NOT NULL AND downtime_hours > 0
                  THEN downtime_hours * 3600000
                ELSE EXTRACT(EPOCH FROM (closed_at - created_at)) * 1000
              END
            )
          ) AS "avgMs",
          COUNT(*) AS count
        FROM logbook
        WHERE hive_id = h.id
          AND maintenance_type = 'Breakdown / Corrective'
          AND status = 'Closed'
          AND closed_at IS NOT NULL
          AND closed_at >= NOW() - INTERVAL '90 days'
        GROUP BY machine
        ORDER BY "avgMs" DESC
      ) r
    ) AS mttr_by_machine,

    NOW() AS computed_at

  FROM hives h
  WHERE EXISTS (
    SELECT 1 FROM hive_members hm
    WHERE hm.hive_id = h.id AND hm.status = 'active'
  )
  ON CONFLICT (hive_id) DO UPDATE SET
    mtbf_by_machine = EXCLUDED.mtbf_by_machine,
    mttr_by_machine = EXCLUDED.mttr_by_machine,
    computed_at     = EXCLUDED.computed_at;
  $$
);
*/
