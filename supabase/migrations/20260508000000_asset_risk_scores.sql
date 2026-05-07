-- Phase ML-1: Asset Risk Scores Table
-- Pre-computed risk scores per asset per hive, written by batch-risk-scoring
-- edge function (daily via pg_cron). UI reads this table directly — no
-- in-browser aggregation, no compute on page load.
--
-- model_version tracks which intelligence layer produced the score:
--   'rules-v1' : Stage 0 rules engine (deterministic, works from Day 1)
--   'ml-v1'    : Stage 1 GBM classifier (activates after 500+ corrective records)

CREATE TABLE IF NOT EXISTS asset_risk_scores (
  id                  uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  hive_id             uuid        REFERENCES hives(id) ON DELETE CASCADE,
  asset_name          text        NOT NULL,
  risk_score          float       NOT NULL CHECK (risk_score >= 0 AND risk_score <= 1),
  risk_level          text        NOT NULL CHECK (risk_level IN ('low','medium','high','critical')),
  health_score        float,
  mtbf_days           float,
  days_until_failure  float,
  top_factors         jsonb       DEFAULT '[]',
  components          jsonb       DEFAULT '{}',
  model_version       text        DEFAULT 'rules-v1',
  generated_at        timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_risk_hive_asset
  ON asset_risk_scores (hive_id, asset_name, generated_at DESC);

CREATE INDEX IF NOT EXISTS idx_risk_hive_level
  ON asset_risk_scores (hive_id, risk_level, generated_at DESC);
