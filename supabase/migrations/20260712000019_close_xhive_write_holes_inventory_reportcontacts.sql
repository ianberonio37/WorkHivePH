-- =============================================================================
-- Cross-hive write-hole sweep — TWO siblings the 2026-07-12 hardening missed.
--
-- LIVE-CONFIRMED EXPLOITS (2026-07-13, rolled-back two-tenant probe;
--   attacker = leandromarquez / Baguio Textile 636cf7e8…, victim = Lucena c9def338…):
--
--   1. `inventory_items_write` — WITH CHECK was
--        (auth.uid() IS NOT NULL AND (auth_uid = auth.uid()
--                                     OR hive_id IN user_supervisor_hive_ids()))
--      The `auth_uid = auth.uid()` owner branch has NO hive gate → an INSERT with
--      auth_uid=self + a FOREIGN hive_id + status <> 'approved' (which dodges the
--      wh_guard_supervisor_approval trigger) short-circuits the OR TRUE → a phantom
--      part is injected into a foreign hive's inventory, feeding its low-stock alerts,
--      reorder points and analytics.  >>> EXPLOIT-1 SUCCEEDED pre-fix (HTTP 201). <<<
--      (Direct analog of the pm_assets fix in 20260712000012 — inventory_items was
--       the sibling left behind.)
--
--   2. `report_contacts_write` — USING was hive-member-scoped but WITH CHECK was only
--        (auth.uid() IS NOT NULL)
--      → any authenticated user INSERTs a report_contact into a FOREIGN hive_id. Read
--      is hive-scoped, so the injected contact surfaces in the victim hive's
--      report-sender recipient list → cross-tenant data-exfil (operational reports can
--      be sent to the attacker's address) + contact-list pollution.
--      >>> EXPLOIT-2 SUCCEEDED pre-fix (HTTP 201). <<<
--
-- FIX (same discipline as 20260712000011/12 + the multitenant-engineer / security skills'
--      "every WITH CHECK must hive-join, never a bare auth.uid() and never an
--       auth_uid = self that ignores hive_id" rule):
--   Hive-gate the owner branch and set each WITH CHECK to constrain hive_id.
--
-- SAFE FOR LEGIT DATA (verified pre-fix, all hives): every inventory_items row has a
--   real auth_uid + a hive the worker is an active member of (0 solo, 0 cross-hive);
--   report_contacts is empty. Service-role/seeder/edge writers (auth.uid() IS NULL)
--   BYPASSRLS → unaffected. The wh_guard_supervisor_approval trigger still governs the
--   status='approved' transition on inventory_items; this only adds the missing hive gate.
-- =============================================================================

-- 1 · inventory_items ----------------------------------------------------------
DROP POLICY IF EXISTS "inventory_items_write" ON public.inventory_items;
CREATE POLICY "inventory_items_write" ON public.inventory_items
  AS PERMISSIVE FOR ALL TO public
  USING (
    auth.uid() IS NOT NULL
    AND (
      (hive_id IS NULL AND auth_uid = auth.uid())                       -- solo item owned by caller
      OR (auth_uid = auth.uid() AND hive_id IN (                        -- own item, in a hive you're an active member of
        SELECT hm.hive_id FROM public.hive_members hm
        WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'))
      OR hive_id IN (SELECT public.user_supervisor_hive_ids())          -- supervisor: any item in your hive
    )
  )
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND (
      (hive_id IS NULL AND auth_uid = auth.uid())
      OR (auth_uid = auth.uid() AND hive_id IN (
        SELECT hm.hive_id FROM public.hive_members hm
        WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'))
      OR hive_id IN (SELECT public.user_supervisor_hive_ids())
    )
  );

-- 2 · report_contacts ----------------------------------------------------------
DROP POLICY IF EXISTS "report_contacts_write" ON public.report_contacts;
CREATE POLICY "report_contacts_write" ON public.report_contacts
  AS PERMISSIVE FOR ALL TO public
  USING (
    auth.uid() IS NOT NULL
    AND hive_id IN (
      SELECT hm.hive_id FROM public.hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  )
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND hive_id IN (                                                    -- was bare `auth.uid() IS NOT NULL` — now hive-gated
      SELECT hm.hive_id FROM public.hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  );
