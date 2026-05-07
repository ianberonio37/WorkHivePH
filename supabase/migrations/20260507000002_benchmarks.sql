-- Phase 3.2: Cross-Hive Benchmark Network tables.
-- hive_benchmarks: each hive's own metrics (private to the hive).
-- network_benchmarks: anonymized aggregate across all hives (no hive ID).

CREATE TABLE IF NOT EXISTS hive_benchmarks (
  id               uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  hive_id          uuid        REFERENCES hives(id) ON DELETE CASCADE,
  equipment_category text      NOT NULL,  -- 'Centrifugal Pump', 'AC Motor', etc.
  mtbf_days        float,                  -- mean time between failures (days)
  mttr_hours       float,                  -- mean time to repair (hours)
  failure_count    int         DEFAULT 0,
  sample_machines  int         DEFAULT 0,  -- distinct machines contributing
  period_days      int         DEFAULT 90,
  computed_at      timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_hive_benchmarks_hive
  ON hive_benchmarks (hive_id, equipment_category, computed_at DESC);

-- One row per category per computation run (replace, don't accumulate)
CREATE UNIQUE INDEX IF NOT EXISTS idx_hive_benchmarks_unique
  ON hive_benchmarks (hive_id, equipment_category);

CREATE TABLE IF NOT EXISTS network_benchmarks (
  id               uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  equipment_category text      NOT NULL,
  industry         text,                   -- 'food_processing', 'cement', etc. or null for all
  avg_mtbf_days    float,
  p25_mtbf_days    float,                  -- 25th percentile (bottom performers)
  p75_mtbf_days    float,                  -- 75th percentile (top performers)
  sample_hives     int         DEFAULT 0,  -- number of hives contributing (min 3 to publish)
  period_days      int         DEFAULT 90,
  computed_at      timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_network_benchmarks_category
  ON network_benchmarks (equipment_category, computed_at DESC);

-- Only the latest benchmark row per category
CREATE UNIQUE INDEX IF NOT EXISTS idx_network_benchmarks_unique
  ON network_benchmarks (equipment_category, COALESCE(industry, ''));
