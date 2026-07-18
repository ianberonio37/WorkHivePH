-- Hive Board Deep Arc (PDDA, 2026-07-10) — I-axis security hardening.
-- Three live-confirmed holes found by the deepwalk's I-axis auditor + verified against
-- pg_policies. This migration ALSO captures policies that existed live-only (drift): the
-- audit-log policy was absent from supabase/migrations/, so a rebuild-from-migrations would
-- have shipped with NO policy (baseline GRANT reopening it). Idempotent (drop-if-exists).

-- ─────────────────────────────────────────────────────────────────────────────
-- 1) hive_audit_log — was ONE cmd=ALL member-RW policy: any active hive member could
--    SELECT (I2 worker-read), UPDATE/DELETE (I5 erase/tamper), and INSERT a forged `actor`
--    (I5 frame-a-supervisor). Fix = APPEND-ONLY + SUPERVISOR-ONLY read + actor bound to
--    the caller's real identity by a trigger.
-- ─────────────────────────────────────────────────────────────────────────────
DROP POLICY IF EXISTS hive_audit_log_hive_rw ON hive_audit_log;
DROP POLICY IF EXISTS hive_audit_log_insert_member ON hive_audit_log;
DROP POLICY IF EXISTS hive_audit_log_select_supervisor ON hive_audit_log;

-- INSERT: any active member of the hive may append (needed by writeAuditLog + the
-- leave-audit flow, which must write member_left BEFORE deleting its own membership).
CREATE POLICY hive_audit_log_insert_member ON hive_audit_log
  FOR INSERT TO public
  WITH CHECK (auth.uid() IS NOT NULL AND hive_id IN (SELECT user_hive_ids()));

-- SELECT: SUPERVISORS ONLY. Closes the worker-readable-audit hole (the client "workers
-- never load this" was a UI-only gate; RLS now enforces it).
CREATE POLICY hive_audit_log_select_supervisor ON hive_audit_log
  FOR SELECT TO public
  USING (auth.uid() IS NOT NULL AND hive_id IN (SELECT user_supervisor_hive_ids()));

-- No UPDATE / DELETE policies => append-only for end users. Retention/maintenance runs
-- as service_role, which bypasses RLS, so purges still work.

-- Bind `actor` to the caller's REAL identity on end-user inserts (kills actor spoofing:
-- a member can no longer forge "actor = <a supervisor>"). service_role / edge-fn writes
-- have auth.uid() = NULL and keep their supplied actor.
CREATE OR REPLACE FUNCTION public.wh_bind_audit_actor()
  RETURNS trigger
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path = public
AS $$
DECLARE real_actor text;
BEGIN
  IF auth.uid() IS NOT NULL THEN
    SELECT display_name INTO real_actor FROM worker_profiles WHERE auth_uid = auth.uid() LIMIT 1;
    IF real_actor IS NOT NULL THEN
      NEW.actor := real_actor;
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS wh_bind_audit_actor_trg ON hive_audit_log;
CREATE TRIGGER wh_bind_audit_actor_trg
  BEFORE INSERT ON hive_audit_log
  FOR EACH ROW EXECUTE FUNCTION public.wh_bind_audit_actor();

-- ─────────────────────────────────────────────────────────────────────────────
-- 2) hives — a leftover permissive anon INSERT policy allowed UNauthenticated hive
--    creation (orphan-row / DoS). Authenticated creation is unaffected (hives_insert,
--    with_check auth.uid() IS NOT NULL, remains).
-- ─────────────────────────────────────────────────────────────────────────────
DROP POLICY IF EXISTS anon_insert_hives ON hives;

-- ─────────────────────────────────────────────────────────────────────────────
-- 3) inventory_items — the write policy's "OR EXISTS(any active member of the hive)"
--    clause let ANY member edit ANY other member's part row (qty/min/name tampering;
--    the approval trigger only guards status->approved). Fix = OWNER or SUPERVISOR only.
--    Supervisor write is preserved so the approval flow (UPDATE a worker's submitted part)
--    still works; the wh_guard_supervisor_approval trigger still guards status transitions.
-- ─────────────────────────────────────────────────────────────────────────────
DROP POLICY IF EXISTS inventory_items_write ON inventory_items;
CREATE POLICY inventory_items_write ON inventory_items
  FOR ALL TO public
  USING (
    auth.uid() IS NOT NULL
    AND (auth_uid = auth.uid() OR hive_id IN (SELECT user_supervisor_hive_ids()))
  )
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND (auth_uid = auth.uid() OR hive_id IN (SELECT user_supervisor_hive_ids()))
  );
