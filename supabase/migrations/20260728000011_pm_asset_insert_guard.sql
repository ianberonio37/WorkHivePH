-- ─────────────────────────────────────────────────────────────────────────────
-- The third and last verb: "Supervisors only" now holds for CREATING a PM asset too.
--
-- FOUND BY THE PM2 WALK (2026-07-28). pm-scheduler's goAddAsset() refuses a non-supervisor in the
-- page, while `pm_assets_write` accepted an INSERT from any active member — probed, a WORKER
-- created a PM asset in their own hive, 1 row. It is the least severe of the three (own hive,
-- self-authored, no cross-tenant reach) and still real: it lets someone the UI says cannot add
-- assets move their hive's PM compliance DENOMINATOR, since every added asset enters the scheduled
-- count that get_pm_compliance_smrp divides by.
--
-- Completes the set: DELETE 20260728000006, UPDATE 20260728000009, INSERT here — one rule, three
-- verbs, all expressed where the write lands instead of in a page anyone can bypass.
--
-- ORDER MATTERS, and this is the second time in the arc it did. This guard is only safe BECAUSE
-- 20260728000010 moved asset-hub's lazy creation (resolvePmAssetId, which builds a pm_asset when an
-- approved RCM strategy is pushed to the PM Scheduler) into a SECURITY DEFINER RPC. Shipping the
-- guard alone would have broken that push for every worker using RCM — the same trap that would
-- have silently stopped all 90 asset renames in PM3. Measure the legitimate callers before
-- tightening a write; twice now the obvious rule would have broken more than the bug it fixed.
--
-- The seeders and any service_role caller keep their reach (auth.uid() IS NULL), and the RCM path
-- runs as definer, so neither is affected.
-- ─────────────────────────────────────────────────────────────────────────────

DROP POLICY IF EXISTS pm_assets_insert_guard ON public.pm_assets;
CREATE POLICY pm_assets_insert_guard
  ON public.pm_assets
  AS RESTRICTIVE
  FOR INSERT
  WITH CHECK (
    -- Solo (hive-less) assets stay self-service.
    (hive_id IS NULL AND auth_uid = auth.uid())
    OR (hive_id IS NOT NULL AND EXISTS (
          SELECT 1 FROM public.hive_members hm
           WHERE hm.hive_id  = pm_assets.hive_id
             AND hm.auth_uid = auth.uid()
             AND hm.status   = 'active'
             AND hm.role     = 'supervisor'
       ))
    OR auth.uid() IS NULL
  );
