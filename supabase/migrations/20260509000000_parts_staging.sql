-- Phase ML-2: Predictive Parts Auto-Staging
-- Recommends parts to pre-stage when an asset crosses risk_score >= 0.7,
-- based on historical parts_used patterns from logbook + parts_records.
-- Written by parts-staging-recommender edge fn (daily, after batch-risk-scoring).
-- Worker accepts a recommendation, which creates a reservation that holds
-- inventory without consuming it until the actual repair logbook entry closes.
--
-- Convention matches asset_risk_scores: no RLS yet (deferred until Supabase Auth
-- migration completes). Schema is hive-scoped via hive_id.

CREATE TABLE IF NOT EXISTS parts_staging_recommendations (
  id            uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  hive_id       uuid        REFERENCES hives(id) ON DELETE CASCADE,
  asset_name    text        NOT NULL,
  risk_score    float       NOT NULL CHECK (risk_score >= 0 AND risk_score <= 1),
  failure_mode  text,
  parts         jsonb       NOT NULL DEFAULT '[]',
  rationale     text,
  confidence    float       CHECK (confidence >= 0 AND confidence <= 1),
  status        text        NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending','accepted','dismissed','expired')),
  generated_at  timestamptz DEFAULT now(),
  expires_at    timestamptz,
  acted_at      timestamptz,
  acted_by      text,
  model_version text        DEFAULT 'rules-v1'
);

CREATE INDEX IF NOT EXISTS idx_psr_hive_status
  ON parts_staging_recommendations (hive_id, status, generated_at DESC);

CREATE INDEX IF NOT EXISTS idx_psr_hive_asset
  ON parts_staging_recommendations (hive_id, asset_name, generated_at DESC);


CREATE TABLE IF NOT EXISTS parts_staged_reservations (
  id                uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  hive_id           uuid        REFERENCES hives(id) ON DELETE CASCADE,
  asset_name        text        NOT NULL,
  item_id           text        NOT NULL,
  qty_reserved      numeric     NOT NULL CHECK (qty_reserved > 0),
  reserved_by       text,
  reserved_at       timestamptz DEFAULT now(),
  consumed_at       timestamptz,
  released_at       timestamptz,
  recommendation_id uuid        REFERENCES parts_staging_recommendations(id) ON DELETE SET NULL,
  notes             text
);

CREATE INDEX IF NOT EXISTS idx_psv_hive_item_active
  ON parts_staged_reservations (hive_id, item_id)
  WHERE consumed_at IS NULL AND released_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_psv_hive_asset
  ON parts_staged_reservations (hive_id, asset_name, reserved_at DESC);


-- Realtime publication: Asset Hub + Alert Hub subscribe to recommendation INSERT/UPDATE
-- Wrapped in DO block because ALTER PUBLICATION fails if table is already a member.
DO $$
BEGIN
  BEGIN
    ALTER PUBLICATION supabase_realtime ADD TABLE parts_staging_recommendations;
  EXCEPTION WHEN duplicate_object THEN NULL;
  END;
  BEGIN
    ALTER PUBLICATION supabase_realtime ADD TABLE parts_staged_reservations;
  EXCEPTION WHEN duplicate_object THEN NULL;
  END;
END $$;
