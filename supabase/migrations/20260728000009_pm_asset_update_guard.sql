-- ─────────────────────────────────────────────────────────────────────────────
-- "Supervisors only" is now true where the write lands, not just in the page.
--
-- FOUND BY THE PM3 WALK (2026-07-28): pm-scheduler gates Edit Asset to supervisors in the CLIENT
-- (`if (HIVE_ROLE !== 'supervisor') { showToast('Supervisors only.'); return; }`) while
-- `pm_assets_write`'s USING is satisfied by ANY active member. Probed live: a WORKER renamed a
-- supervisor's asset to 'HIJACKED' and set its criticality to Low. One row, no error.
--
-- That is consequential, not cosmetic: `criticality` feeds risk scoring, triage order and alert
-- severity, and `asset_name` is how every surface identifies the machine. Same UI-only-gate class
-- as the PM12 delete hole (20260728000006), which this mirrors deliberately — one rule, two verbs.
--
-- ORDER MATTERS: this migration is only safe BECAUSE 20260728000008 moved the legitimate
-- asset-rename propagation (logbook.html's syncToPMAssets) into a SECURITY DEFINER RPC. Applying
-- this guard alone would have silently stopped that propagation for every asset on the platform —
-- measured, all 90 pm_asset<->node pairs have a node author who is neither the pm_asset's author
-- nor a supervisor — and because a 0-row UPDATE is not an error, nothing would have reported it.
-- The names would have quietly diverged between asset_nodes and pm_assets.
--
-- The RESTRICTIVE form ANDs with the existing permissive policy, so it cannot widen anything, and
-- it can be dropped independently to prove the gate has teeth.
-- ─────────────────────────────────────────────────────────────────────────────

DROP POLICY IF EXISTS pm_assets_update_guard ON public.pm_assets;
CREATE POLICY pm_assets_update_guard
  ON public.pm_assets
  AS RESTRICTIVE
  FOR UPDATE
  USING (
    (hive_id IS NULL AND auth_uid = auth.uid())
    OR (hive_id IS NOT NULL AND (
          auth_uid = auth.uid()
          OR EXISTS (
            SELECT 1 FROM public.hive_members hm
             WHERE hm.hive_id  = pm_assets.hive_id
               AND hm.auth_uid = auth.uid()
               AND hm.status   = 'active'
               AND hm.role     = 'supervisor'
          )
       ))
    -- service_role / psql / the seeders keep their reach; RLS is not the tool for restraining a
    -- trusted backend, and the identity-sync RPC runs as definer.
    OR auth.uid() IS NULL
  );
