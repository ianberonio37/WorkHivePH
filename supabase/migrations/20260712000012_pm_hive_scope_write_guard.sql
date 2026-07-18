-- =============================================================================
-- PM Scheduler PDDA Arc — I-axis keystone: close THREE cross-hive write holes.
--
-- LIVE-CONFIRMED EXPLOITS (2026-07-12, rolled-back two-tenant probe;
--   attacker = leandromarquez / Baguio Textile 636cf7e8…, victim = Lucena c9def338…):
--   1. `pm_scope_items_write` — USING was parent-asset-scoped (asset_id IN pm_assets
--      JOIN hive_members) but WITH CHECK was only `(auth.uid() IS NOT NULL)`. INSERT
--      is checked by WITH CHECK, NOT USING → a worker injected a PM scope item onto a
--      FOREIGN hive's asset (unplanned PM tasks smuggled into another plant's schedule).
--      >>> EXPLOIT-1 SUCCEEDED pre-fix. <<<
--   2. `pm_completions_write` — WITH CHECK was NULL → falls back to USING
--      (`auth_uid = auth.uid()`), which has NO hive gate → a self-attributed completion
--      injected into a FOREIGN hive's compliance (poisons v_pm_compliance_truth →
--      analytics %, shift-planner PMs-due, hive PM-Health, predictive PM-overdue).
--      >>> EXPLOIT-2 SUCCEEDED pre-fix. <<<
--   3. `pm_assets_write` — WITH CHECK was NULL → falls back to USING
--      (`auth_uid = auth.uid() OR member-of(hive)`), an OR. Inserting with auth_uid=self
--      + a FOREIGN hive_id short-circuits the OR TRUE → a phantom asset injected into a
--      foreign hive's PM asset list (and scope items can then be hung off it).
--      >>> EXPLOIT-3 SUCCEEDED pre-fix (only a NOT-NULL on worker_name, never RLS,
--          had stopped the first attempt). <<<
--
-- FIX (same discipline as 20260712000011 inventory ledger guard + the child/ledger-table
--      WITH-CHECK rule in the security + multitenant-engineer skills):
--   Every write policy's WITH CHECK must membership-join the PARENT / own hive — never a
--   bare `auth.uid() IS NOT NULL` and never an `auth_uid = self` that ignores hive_id.
--   USING is also tightened to the read-policy shape (hive-member OR solo-owner), dropping
--   any bare `auth_uid = self` branch that let a stale creator touch a hive row.
--
-- SAFE FOR LEGIT DATA (verified pre-fix, all hives): 0 solo assets · 0 null-auth_uid
--   assets · 0 scope/completion hive-mismatch vs parent asset · 0 orphans · 0 null-hive.
-- Service-role/seeder/edge-fn writers (auth.uid() IS NULL) BYPASSRLS → unaffected.
-- =============================================================================

-- 1 · pm_scope_items -----------------------------------------------------------
DROP POLICY IF EXISTS "pm_scope_items_write" ON public.pm_scope_items;
CREATE POLICY "pm_scope_items_write" ON public.pm_scope_items
  AS PERMISSIVE FOR ALL TO public
  USING (
    auth.uid() IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.pm_assets pa
      WHERE pa.id = pm_scope_items.asset_id
        AND (
          (pa.hive_id IS NULL AND pa.auth_uid = auth.uid())
          OR pa.hive_id IN (
            SELECT hm.hive_id FROM public.hive_members hm
            WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
          )
        )
    )
  )
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.pm_assets pa
      WHERE pa.id = pm_scope_items.asset_id
        AND pa.hive_id IS NOT DISTINCT FROM pm_scope_items.hive_id   -- scope hive must match its asset's hive
        AND (
          (pa.hive_id IS NULL AND pa.auth_uid = auth.uid())
          OR pa.hive_id IN (
            SELECT hm.hive_id FROM public.hive_members hm
            WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
          )
        )
    )
  );

-- 2 · pm_completions -----------------------------------------------------------
DROP POLICY IF EXISTS "pm_completions_write" ON public.pm_completions;
CREATE POLICY "pm_completions_write" ON public.pm_completions
  AS PERMISSIVE FOR ALL TO public
  USING (
    auth.uid() IS NOT NULL
    AND auth_uid = auth.uid()                                        -- own attribution (UPDATE/DELETE only your rows)
  )
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND auth_uid = auth.uid()
    AND (
      (hive_id IS NULL AND EXISTS (                                  -- solo path: asset is solo & owned by caller
        SELECT 1 FROM public.pm_assets pa
        WHERE pa.id = pm_completions.asset_id
          AND pa.hive_id IS NULL AND pa.auth_uid = auth.uid()))
      OR (hive_id IN (                                               -- hive path: completion's hive is one you're in …
        SELECT hm.hive_id FROM public.hive_members hm
        WHERE hm.auth_uid = auth.uid() AND hm.status = 'active')
        AND EXISTS (                                                 -- … and the referenced asset lives in THAT hive
          SELECT 1 FROM public.pm_assets pa
          WHERE pa.id = pm_completions.asset_id
            AND pa.hive_id IS NOT DISTINCT FROM pm_completions.hive_id))
    )
  );

-- 3 · pm_assets ----------------------------------------------------------------
DROP POLICY IF EXISTS "pm_assets_write" ON public.pm_assets;
CREATE POLICY "pm_assets_write" ON public.pm_assets
  AS PERMISSIVE FOR ALL TO public
  USING (
    auth.uid() IS NOT NULL
    AND (
      (hive_id IS NULL AND auth_uid = auth.uid())
      OR hive_id IN (
        SELECT hm.hive_id FROM public.hive_members hm
        WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
      )
    )
  )
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND (
      (hive_id IS NULL AND auth_uid = auth.uid())                    -- solo asset owned by caller
      OR hive_id IN (                                                -- hive asset: caller must be an active member
        SELECT hm.hive_id FROM public.hive_members hm
        WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
      )
    )
  );
