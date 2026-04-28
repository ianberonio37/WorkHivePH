-- Add production_output field to logbook
-- Enables OEE Quality and Performance dimensions (ISO 22400-2)
-- Schema: { "good_units": 1850, "total_units": 2000, "quality_pct": 92.5 }
-- Shown only for Closed Breakdown entries
-- NULL = not recorded (optional field, legacy rows unaffected)

ALTER TABLE logbook
  ADD COLUMN IF NOT EXISTS production_output jsonb;
