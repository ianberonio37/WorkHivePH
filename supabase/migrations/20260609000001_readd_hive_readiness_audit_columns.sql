-- Re-add the 6 hive_readiness_audit columns that 20260520000004_drop_phantom_columns_safe.sql
-- wrongly dropped as "never wired (hive readiness audit)".
--
-- ROOT CAUSE: tools/audit_phantom_columns.py classifies a column as a phantom
-- by scanning FRONTEND + EDGE consumers (db.from(...).select / .insert). It does
-- NOT scan plpgsql function bodies (pg_proc.prosrc). The compute_hive_readiness
-- RPC (migration 20260513000001) is a consumer of all six columns:
--   * SELECT new_stair, new_composite ... ORDER BY changed_at DESC   (prior snapshot)
--   * INSERT (previous_stair, new_stair, previous_composite, new_composite,
--             reason, evidence_delta)                                (audit row)
-- so the drop made the RPC fail with 42703 "column \"new_stair\" does not exist",
-- which broke the hive.html Maturity Stairway card for every hive lacking a
-- pre-existing readiness snapshot (compute → 400 → card renders empty forever).
--
-- A pg_proc.prosrc scan confirms compute_hive_readiness is the ONLY casualty of
-- 20260520000004 — the other dropped columns (quotas / avatar / language /
-- phase-6 scaffolding) are referenced by no function.
--
-- Forward-only. Idempotent (ADD COLUMN IF NOT EXISTS). The two columns the
-- original 20260513000001 schema marked NOT NULL (new_stair, new_composite) are
-- re-added NULLABLE here so the migration is safe on any environment whose table
-- already holds rows written before the drop (those rows lost the column data and
-- cannot satisfy a NOT NULL backfill). The compute_hive_readiness RPC always
-- supplies both on INSERT, so new rows remain fully populated in practice.

BEGIN;

ALTER TABLE public.hive_readiness_audit
  ADD COLUMN IF NOT EXISTS changed_at         timestamptz NOT NULL DEFAULT now(),
  ADD COLUMN IF NOT EXISTS previous_stair     smallint,
  ADD COLUMN IF NOT EXISTS new_stair          smallint,
  ADD COLUMN IF NOT EXISTS previous_composite smallint,
  ADD COLUMN IF NOT EXISTS new_composite      smallint,
  ADD COLUMN IF NOT EXISTS evidence_delta     jsonb;

-- Restore the forensic-trail index the drop removed with changed_at.
CREATE INDEX IF NOT EXISTS idx_hive_readiness_audit_hive_when
  ON public.hive_readiness_audit (hive_id, changed_at DESC);

-- Restore the stair-range guard (NULL passes a CHECK, so this is safe with the
-- nullable new_stair above). Guarded so the migration stays idempotent.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'public.hive_readiness_audit'::regclass
      AND conname = 'hra_stair_range'
  ) THEN
    ALTER TABLE public.hive_readiness_audit
      ADD CONSTRAINT hra_stair_range CHECK (new_stair BETWEEN 0 AND 4);
  END IF;
END$$;

COMMIT;
