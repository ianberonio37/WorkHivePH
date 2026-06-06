-- ============================================================================
-- 20260607000006  Lock export_hive_data to service_role (supervisor-enforced
--                 upstream by the export-hive-data edge fn)
-- ============================================================================
-- Follow-up to the SECURITY DEFINER hardening (0003-0005). export_hive_data
-- dumps an ENTIRE hive (members/logbook/PM/assets/audit/...) to JSON. Its only
-- caller is the `export-hive-data` edge fn, which already enforces an ACTIVE
-- SUPERVISOR membership check (checkSupervisor) before invoking it via the
-- service role. (hive.html only references the name as an audit-log icon label,
-- not a call.)
--
-- Migration 0005 gave it an in-function MEMBER gate, but the intended policy is
-- SUPERVISOR-only -- a member-level gate is too weak, and leaving it callable by
-- `authenticated` lets any member bypass the edge fn's supervisor check via a
-- direct PostgREST call. The correct boundary for a backend-only, supervisor-
-- gated export is the GRANT: service_role only. The in-fn member gate from 0005
-- remains as harmless defense-in-depth.
--
-- Skills: security, multitenant-engineer, enterprise-compliance. Deploy PENDING.
-- ============================================================================

BEGIN;

REVOKE EXECUTE ON FUNCTION public.export_hive_data(uuid) FROM PUBLIC, anon, authenticated;
GRANT  EXECUTE ON FUNCTION public.export_hive_data(uuid) TO service_role;

COMMIT;
