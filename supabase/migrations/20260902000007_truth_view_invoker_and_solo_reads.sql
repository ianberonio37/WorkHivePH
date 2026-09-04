-- VEHICLE SEED M4b (2026-09-02): three holes the solo path exposed, one of them MINE.
--
-- 1. 20260902000006's CREATE OR REPLACE of v_pm_scope_items_truth silently STRIPPED
--    security_invoker (every other truth view on the platform carries it) — the view ran
--    definer-rights, and `SET ROLE anon; SELECT count(*)` returned ALL 437 scope rows.
--    A live cross-tenant read hole, open since that migration applied earlier today.
--    Lesson (security_invoker family): CREATE OR REPLACE VIEW resets reloptions — every
--    view REPLACE must re-assert the option in the same migration.
--
-- 2. pm_scope_items_read has NO solo branch (it joins through hive_members), so a solo
--    owner's PM checklist — writable via the solo branch pm_scope_items_write already has —
--    is INVISIBLE on read: the write-only trap. With invoker rights restored on the truth
--    view, this would black out the entire PM surface for a solo vehicle owner.
--
-- 3. inventory_items_read has the same hole: solo write branch exists, no solo read branch.
--    A solo owner's starter parts would seed and then vanish from every inventory surface.

ALTER VIEW public.v_pm_scope_items_truth SET (security_invoker = true);

DROP POLICY IF EXISTS pm_scope_items_read ON public.pm_scope_items;
CREATE POLICY pm_scope_items_read ON public.pm_scope_items
  FOR SELECT USING (
    auth.uid() IS NOT NULL
    AND (
      -- solo: the parent pm_asset is hive-less and mine
      asset_id IN (
        SELECT pa.id FROM public.pm_assets pa
        WHERE pa.hive_id IS NULL AND pa.auth_uid = auth.uid()
      )
      -- hive: unchanged — any active member of the asset's hive
      OR asset_id IN (
        SELECT pa.id
        FROM public.pm_assets pa
        JOIN public.hive_members hm ON pa.hive_id = hm.hive_id
        WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
      )
    )
  );

DROP POLICY IF EXISTS inventory_items_read ON public.inventory_items;
CREATE POLICY inventory_items_read ON public.inventory_items
  FOR SELECT USING (
    auth.uid() IS NOT NULL
    AND (
      (hive_id IS NULL AND auth_uid = auth.uid())
      OR hive_id IN (
        SELECT hm.hive_id FROM public.hive_members hm
        WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
      )
    )
  );
