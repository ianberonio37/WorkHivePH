-- =============================================================================
-- cmms_audit_log — make the CMMS import-audit trail APPEND-ONLY.
--
-- Found in the 2026-07-13 bug-hunt: `cmms_audit_log_hive_rw` was FOR ALL with
-- USING/WITH CHECK = `hive_id IN user_hive_ids()` — i.e. any active hive member could
-- UPDATE (falsify rows_written / quality_score / operation) or DELETE (erase evidence of
-- a CMMS import) their hive's audit rows. An audit trail must be append-only. Siblings
-- `hive_audit_log` already got append-only + actor-bound hardening; cmms_audit_log didn't.
--
-- FIX: replace the FOR ALL policy with INSERT + SELECT only (members log + read their
-- hive's imports). No UPDATE / DELETE policy exists, so clients cannot mutate or erase a
-- row. The service_role writer / seeder (auth.uid() IS NULL → BYPASSRLS) is unaffected and
-- remains the only path that can correct/prune the log. Cross-hive stays blocked.
-- =============================================================================

DROP POLICY IF EXISTS "cmms_audit_log_hive_rw" ON public.cmms_audit_log;

DROP POLICY IF EXISTS "cmms_audit_log_insert" ON public.cmms_audit_log;
CREATE POLICY "cmms_audit_log_insert" ON public.cmms_audit_log
  AS PERMISSIVE FOR INSERT TO public
  WITH CHECK (auth.uid() IS NOT NULL AND hive_id IN (SELECT public.user_hive_ids()));

DROP POLICY IF EXISTS "cmms_audit_log_select" ON public.cmms_audit_log;
CREATE POLICY "cmms_audit_log_select" ON public.cmms_audit_log
  AS PERMISSIVE FOR SELECT TO public
  USING (auth.uid() IS NOT NULL AND hive_id IN (SELECT public.user_hive_ids()));
-- (intentionally NO update/delete policy => the trail is append-only for all clients)
