-- =============================================================================
-- Intra-hive privilege-escalation sweep — role gate missing on 3 sibling tables.
--
-- The 2026-07 hardening supervisor-scoped integration_configs but LEFT member-RW
-- (`hive_id IN user_hive_ids()`, no role gate, no approval trigger) on siblings whose
-- writes are privileged. Cross-hive is already blocked; the gap is WITHIN the hive.
--
-- LIVE-CONFIRMED (2026-07-13, worker session = bryangarcia / Baguio 636cf7e8…, a
--   NON-supervisor): a worker minted a programmatic hive-data credential —
--   `api_keys` INSERT succeeded (HTTP 201). >>> EXPLOIT SUCCEEDED pre-fix. <<<
--   (A worker could equally revoke existing keys = integration DoS.)
--
-- Same member-RW-no-role-gate shape (verified via pg_policies + no guarding trigger):
--   • api_keys_hive_rw               — mint/revoke hive API credentials
--   • project_roles_hive_rw          — assign/remove project role grants
--   • project_change_orders_hive_rw  — approve/reject change-order cost/schedule impact
--
-- FIX:
--   • api_keys, project_roles → supervisor-scoped ALL policy (copy of the
--     integration_configs_supervisor_all shape). These writes are wholly admin actions.
--   • project_change_orders → KEEP member-RW so a worker can still RAISE a change order,
--     but attach the proven generic wh_guard_supervisor_approval trigger so only an
--     active supervisor of the row's hive can set status='approved'/approved_by/approved_at
--     (or delete a signed-off CO). Mirrors the pm_completions / rcm_* / logbook guard.
--
-- SAFE FOR LEGIT DATA: all three tables are EMPTY (0 rows) at fix time. Service-role /
--   seeder / edge writers (auth.uid() IS NULL) BYPASSRLS and the trigger early-returns.
-- =============================================================================

-- 1 · api_keys — supervisor-only mint/revoke ----------------------------------
DROP POLICY IF EXISTS "api_keys_hive_rw" ON public.api_keys;
CREATE POLICY "api_keys_supervisor_all" ON public.api_keys
  AS PERMISSIVE FOR ALL TO public
  USING (
    auth.uid() IS NOT NULL AND EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = api_keys.hive_id AND hm.auth_uid = auth.uid()
        AND hm.role = 'supervisor' AND hm.status = 'active')
  )
  WITH CHECK (
    auth.uid() IS NOT NULL AND EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = api_keys.hive_id AND hm.auth_uid = auth.uid()
        AND hm.role = 'supervisor' AND hm.status = 'active')
  );

-- 2 · project_roles — supervisor-only assign/remove ---------------------------
DROP POLICY IF EXISTS "project_roles_hive_rw" ON public.project_roles;
CREATE POLICY "project_roles_supervisor_all" ON public.project_roles
  AS PERMISSIVE FOR ALL TO public
  USING (
    auth.uid() IS NOT NULL AND EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = project_roles.hive_id AND hm.auth_uid = auth.uid()
        AND hm.role = 'supervisor' AND hm.status = 'active')
  )
  WITH CHECK (
    auth.uid() IS NOT NULL AND EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = project_roles.hive_id AND hm.auth_uid = auth.uid()
        AND hm.role = 'supervisor' AND hm.status = 'active')
  );

-- 3 · project_change_orders — worker may RAISE, only supervisor may APPROVE ----
--    (member-RW policy project_change_orders_hive_rw is kept as-is; add the guard.)
DROP TRIGGER IF EXISTS tg_guard_approval_project_co ON public.project_change_orders;
CREATE TRIGGER tg_guard_approval_project_co
  BEFORE INSERT OR UPDATE OR DELETE ON public.project_change_orders
  FOR EACH ROW EXECUTE FUNCTION public.wh_guard_supervisor_approval();
