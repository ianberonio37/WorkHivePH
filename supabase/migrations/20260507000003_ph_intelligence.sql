-- Phase 5.1: Philippine Industrial Intelligence Report
-- Stores generated reports (monthly / quarterly aggregate across all hives).
-- api_keys: per-hive authentication for the WorkHive Intelligence API.

CREATE TABLE IF NOT EXISTS ph_intelligence_reports (
  id            uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  period        text        NOT NULL,         -- e.g. '2026-Q2' or '2026-05'
  period_type   text        DEFAULT 'monthly', -- 'monthly' | 'quarterly'
  hive_count    int         DEFAULT 0,
  wo_count      int         DEFAULT 0,
  equipment_count int       DEFAULT 0,
  report_json   jsonb,                         -- structured data (benchmarks, patterns)
  narrative     jsonb,                         -- AI-generated text sections
  generated_at  timestamptz DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_ph_reports_period
  ON ph_intelligence_reports (period);

-- WorkHive Intelligence API keys (Phase 5.3)
CREATE TABLE IF NOT EXISTS api_keys (
  id           uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  hive_id      uuid        REFERENCES hives(id) ON DELETE CASCADE,
  key_prefix   text        NOT NULL,   -- first 8 chars shown in UI (wh_abc123)
  key_hash     text        NOT NULL,   -- sha256 hash of the full key
  label        text,
  enabled      boolean     DEFAULT true,
  call_count   int         DEFAULT 0,
  last_used_at timestamptz,
  created_at   timestamptz DEFAULT now(),
  UNIQUE (key_hash)
);

CREATE INDEX IF NOT EXISTS idx_api_keys_hive
  ON api_keys (hive_id);
