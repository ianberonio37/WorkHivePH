-- 20260621000000_account_deactivation.sql
-- Arc I I8/I — GDPR/PDPA account offboarding: SOFT-DEACTIVATE + ANONYMIZE (Ian's chosen model, 2026-06-21).
--
-- Right-to-erasure of PERSONAL data without destroying maintenance history:
--   * anonymize the caller's PII on the identity anchor (display_name -> 'Deleted user', email -> NULL),
--   * mark every membership 'deactivated' so the identity can't re-enter a hive,
--   * PRESERVE operational records (logbook / pm_completions / engineering_calcs / ...) for hive
--     history + audit integrity — only the PII link is anonymized.
--
-- Security posture (carries the prior arcs' lessons):
--   * SELF-SCOPED by auth.uid() with NO parameter -> no cross-user IDOR (Arc G/H DEFINER-gate lesson).
--   * SECURITY DEFINER + SET search_path = pg_catalog, public  (CVE-2018-1058 lockdown; function-security gate).
--   * REVOKE from PUBLIC + anon, GRANT to authenticated + service_role  (Arc H PUBLIC-default blind spot:
--     revoking anon/authenticated alone leaves PUBLIC holding the grant).
--   * Login-ban of the auth.users row is the Supabase admin-API residual (service-role / dashboard) =
--     the named attributed ceiling; this RPC does the in-DB anonymize + access revoke.

ALTER TABLE public.worker_profiles
  ADD COLUMN IF NOT EXISTS deactivated_at timestamptz;

-- Allow the self-offboarding lifecycle state. The status CHECK (added by 20260510000006) only permitted
-- 'active'/'kicked'; 'deactivated' is the user-initiated state (distinct from supervisor 'kicked') that
-- blocks hive re-entry the same way. Idempotent drop+recreate. (Caught live: the constraint rejected
-- 'deactivated' until this was added — the static validator couldn't see the post-baseline constraint.)
ALTER TABLE public.hive_members DROP CONSTRAINT IF EXISTS hive_members_status_check;
ALTER TABLE public.hive_members ADD CONSTRAINT hive_members_status_check
  CHECK (status IN ('active', 'kicked', 'deactivated'));

CREATE OR REPLACE FUNCTION public.deactivate_my_account()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  uid uuid := auth.uid();
BEGIN
  IF uid IS NULL THEN
    RAISE EXCEPTION 'not authenticated';
  END IF;

  -- Anonymize personal data on the identity anchor. Username stays (it is the synthetic-email login
  -- key `username@auth.workhiveph.com`, not real PII); the optional real email + the human display
  -- name are the personal data, and both are erased here.
  UPDATE public.worker_profiles
     SET display_name   = 'Deleted user',
         email          = NULL,
         deactivated_at = now()
   WHERE auth_uid = uid;

  -- Revoke hive access: every membership -> 'deactivated' (validateHiveMembership treats any non-'active'
  -- status as no access, so the deactivated identity is blocked on next load). Operational rows are
  -- intentionally PRESERVED — they carry the hive's maintenance history, not the user's personal data.
  UPDATE public.hive_members
     SET status = 'deactivated'
   WHERE auth_uid = uid;
END;
$$;

REVOKE ALL ON FUNCTION public.deactivate_my_account() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.deactivate_my_account() FROM anon;
GRANT EXECUTE ON FUNCTION public.deactivate_my_account() TO authenticated, service_role;
