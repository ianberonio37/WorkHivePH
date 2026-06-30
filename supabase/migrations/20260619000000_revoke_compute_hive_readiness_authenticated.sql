-- Security: close a cross-tenant exposure on compute_hive_readiness.
--
-- compute_hive_readiness(uuid) is the SECURITY DEFINER *write/compute* path (it snapshots a
-- hive's readiness; comment in 20260513000001 calls it "the update path"). It was GRANTed to
-- `authenticated` in 20260513000001:425 with NO in-function membership gate, so a logged-in user
-- could call compute_hive_readiness(<victim_hive_id>) and trigger a compute/write against another
-- hive — the one ungated DEFINER hive-fn (the other 16 carry an in-fn hive_members gate; flagged by
-- validate_definer_membership_gate.py as a REG after a Jun-09 CREATE-OR-REPLACE dropped its posture).
--
-- The browser-facing READ path is get_hive_readiness_current(uuid), which IS gated. No browser/edge
-- code invokes compute_hive_readiness directly (verified by repo grep) — it runs server-side
-- (cron / service-role). So the minimal, safe fix is backend-only: REVOKE from authenticated,
-- keep service_role. Matches the validator's "REVOKE EXECUTE FROM anon/authenticated for
-- backend-only RPCs" remediation.
REVOKE EXECUTE ON FUNCTION public.compute_hive_readiness(uuid) FROM authenticated;
REVOKE EXECUTE ON FUNCTION public.compute_hive_readiness(uuid) FROM anon;
