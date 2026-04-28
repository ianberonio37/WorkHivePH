-- Priority 2: Indexes on new analytics logbook columns
-- Added in session Apr 28 2026: failure_consequence, readings_json, production_output
-- Rule (Performance skill): every column used in .eq(), GROUP BY, or WHERE needs an index.
-- Rule (Architect skill): add indexes at migration time, not after it feels slow.

-- ── BTREE indexes for filtering / grouping ────────────────────────────────────

-- failure_consequence — used in RCM consequence distribution (GROUP BY)
-- Allows fast grouping: "how many Stopped production vs Safety risk failures?"
CREATE INDEX IF NOT EXISTS idx_logbook_consequence
  ON logbook (hive_id, failure_consequence)
  WHERE failure_consequence IS NOT NULL;

-- ── GIN indexes for JSONB querying ───────────────────────────────────────────

-- readings_json — used for anomaly detection and sensor queries
-- Without GIN, querying inside JSONB (e.g. temperature > 80) is a full table scan.
-- GIN enables: WHERE readings_json @> '{"temperature_c": 85}'
CREATE INDEX IF NOT EXISTS idx_logbook_readings_gin
  ON logbook USING GIN (readings_json)
  WHERE readings_json IS NOT NULL;

-- production_output — used for OEE Quality queries
-- Enables: WHERE production_output @> '{"quality_pct": ...}'
CREATE INDEX IF NOT EXISTS idx_logbook_production_gin
  ON logbook USING GIN (production_output)
  WHERE production_output IS NOT NULL;

-- ── Supporting indexes for analytics queries ──────────────────────────────────

-- worker_name on logbook — analytics frequently filters solo workers
-- (hive_id queries already covered by existing indexes)
CREATE INDEX IF NOT EXISTS idx_logbook_worker_date
  ON logbook (worker_name, created_at DESC)
  WHERE hive_id IS NULL;  -- partial index: only for solo-mode entries

-- pm_completions: completed_at for period-scoped compliance queries
-- The compliance fix filters completions by period — needs this index
CREATE INDEX IF NOT EXISTS idx_pm_completions_asset_date
  ON pm_completions (asset_id, completed_at DESC);

-- inventory_transactions: already filtered by hive_id + type + created_at
CREATE INDEX IF NOT EXISTS idx_inv_txns_hive_type_date
  ON inventory_transactions (hive_id, type, created_at DESC)
  WHERE type = 'use';  -- partial index: analytics only queries 'use' type

-- ── COMMENT: When to add a GIN index ─────────────────────────────────────────
-- Use GIN (not BTREE) when:
--   1. Querying INSIDE a JSONB column (key existence, value comparison)
--   2. Full-text search on a text column
-- Use BTREE (default) when:
--   1. Equality, range, or sort on a scalar column
--   2. Partial filtering (WHERE col IS NOT NULL)
-- GIN indexes are larger and slower to write but much faster to query JSONB.
