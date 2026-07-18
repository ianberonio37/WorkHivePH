-- 20260712000013_intelligence_write_guard.sql
-- Asset/Alert/Shift PDDA arc (2026-07-12) — I-axis (integrity) keystone.
--
-- F11 (LIVE-EXPLOITED): asset_risk_scores.asset_risk_scores_hive_rw was a `FOR ALL` policy
-- whose USING == WITH CHECK == "any active member of the row's hive". A live rolled-back
-- probe as a real authenticated WORKER confirmed a member can both INSERT a fabricated row
-- and UPDATE an existing row's risk_score/risk_level in their own hive (cross-hive was already
-- blocked). This is the nightly-batch-owned risk cache that FEEDS asset-hub risk chips,
-- alert-hub risk alerts, shift-brain top-risk, and analytics — a worker could fabricate a
-- "critical" or bury a real "critical" as "low", poisoning every downstream consumer.
-- The sibling caches sensor_readings and anomaly_signals already lock all client writes
-- (INSERT WITH CHECK false, UPDATE/DELETE USING false) — the batch writers use the
-- service-role key (BYPASSRLS), so locking client writes does NOT affect the producer.
-- Fix: align asset_risk_scores to that pattern (SELECT hive-member-scoped; INSERT/UPDATE/
-- DELETE service-role-only).
--
-- F10 (DEFENSE-IN-DEPTH, latent): asset_nodes_write's USING owner-branch `auth_uid = auth.uid()`
-- had NO hive gate, so a member who LEFT a hive could still act (notably DELETE, authorized by
-- USING alone) on their own non-approved authored rows there. Tighten the owner-branch to also
-- require active membership of the row's hive. Approval columns remain trigger-gated
-- (tg_guard_approval). WITH CHECK stays hive-membership-scoped (unchanged — legit supervisor
-- approval of a worker's submission must keep working).
--
-- Idempotent: DROP POLICY IF EXISTS before each CREATE. Verified by the LIVE two-tenant gate
-- validate_intelligence_write_isolation.py (rolled-back probe, reseed-robust).

-- ── F11: asset_risk_scores — lock client writes (service-role batch only) ──────────────────
DROP POLICY IF EXISTS asset_risk_scores_hive_rw       ON public.asset_risk_scores;
DROP POLICY IF EXISTS asset_risk_scores_read          ON public.asset_risk_scores;
DROP POLICY IF EXISTS asset_risk_scores_insert_locked ON public.asset_risk_scores;
DROP POLICY IF EXISTS asset_risk_scores_update_locked ON public.asset_risk_scores;
DROP POLICY IF EXISTS asset_risk_scores_delete_locked ON public.asset_risk_scores;

CREATE POLICY asset_risk_scores_read ON public.asset_risk_scores
  FOR SELECT USING (
    auth.uid() IS NOT NULL
    AND hive_id IN (
      SELECT hm.hive_id FROM public.hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  );

-- Writes are service-role only (the nightly batch bypasses RLS). No client path may write.
CREATE POLICY asset_risk_scores_insert_locked ON public.asset_risk_scores
  FOR INSERT WITH CHECK (false);
CREATE POLICY asset_risk_scores_update_locked ON public.asset_risk_scores
  FOR UPDATE USING (false) WITH CHECK (false);
CREATE POLICY asset_risk_scores_delete_locked ON public.asset_risk_scores
  FOR DELETE USING (false);

-- ── F10: asset_nodes — hive-gate the USING owner-branch (defense-in-depth on DELETE) ───────
DROP POLICY IF EXISTS asset_nodes_write ON public.asset_nodes;
CREATE POLICY asset_nodes_write ON public.asset_nodes
  FOR ALL
  USING (
    auth.uid() IS NOT NULL
    AND (
      -- owner branch NOW requires active membership of the row's hive (was ungated —
      -- a departed member could still DELETE their own non-approved authored rows)
      (asset_nodes.auth_uid = auth.uid() AND asset_nodes.hive_id IN (
         SELECT hm.hive_id FROM public.hive_members hm
         WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'))
      OR EXISTS (
        SELECT 1 FROM public.hive_members hm
        WHERE hm.hive_id = asset_nodes.hive_id
          AND hm.auth_uid = auth.uid()
          AND hm.role = 'supervisor'
          AND hm.status = 'active')
    )
  )
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND asset_nodes.hive_id IN (
      SELECT hm.hive_id FROM public.hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  );
