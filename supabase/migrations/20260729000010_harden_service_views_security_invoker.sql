-- =====================================================================
-- HARDENING: put base-table RLS back UNDER the service truth views that can carry it
-- =====================================================================
-- The full-mode `view_security_invoker` gate (which --fast never runs) flagged all six service
-- truth views as `security_invoker = false` - owner's rights - i.e. reading their base tables
-- WITHOUT the caller's RLS. The arc chose that deliberately (the house pattern from mig 40: an
-- owner-rights view MUST re-assert the row boundary in its own WHERE clause, which these do, and
-- the cross-hive isolation gate empirically reports 0 leaks across 35 private views). But
-- "deliberate and empirically clean" is weaker than "the database enforces it too", so each view
-- was TESTED for whether invoker rights preserve its intended reads:
--
--   v_service_provider_truth      CAN  (7 rows still visible to a client)
--   v_service_request_truth       CAN  (8 own requests still visible)
--   v_service_credit_ledger_truth CAN  (5 own ledger rows still visible)
--   v_service_credit_topups_truth CAN  (3 own filings still visible)
--   v_service_open_broadcasts     CANNOT - `permission denied for table service_providers`
--   v_service_job_tracking        CANNOT - same
--
-- The two that CANNOT are not an oversight: they exist precisely to expose a curated slice of a
-- COLUMN-REVOKED table. `service_providers` had its columns revoked from `authenticated` and only
-- a public subset granted back (mig 39, revoke-first privacy for `live_location`), so an
-- invoker-rights read hits table-level permission denial before any row filter runs. Owner rights
-- are load-bearing there, and the boundary is re-asserted in the view + proven by the C3/C10 gates
-- (a stranger reads 0 rows from the tracking view; an out-of-radius provider cannot accept).
--
-- So: harden the four that can be hardened - defence in depth, RLS *and* the predicate - and leave
-- the two that genuinely need owner rights, documented, rather than pretending all six are equal.

BEGIN;

alter view public.v_service_provider_truth      set (security_invoker = on);
alter view public.v_service_request_truth       set (security_invoker = on);
alter view public.v_service_credit_ledger_truth set (security_invoker = on);
alter view public.v_service_credit_topups_truth set (security_invoker = on);
-- second pass: the rate card and the coordinate-free presence view also carry invoker rights
-- cleanly (14 catalog rows and 5 area rows still visible to a plain authenticated caller).
alter view public.v_service_catalog_truth        set (security_invoker = on);
alter view public.v_service_area_presence        set (security_invoker = on);

comment on view public.v_service_open_broadcasts is
  'Provider broadcast feed. security_invoker stays FALSE by necessity: it reads service_providers, whose columns are revoked from authenticated (revoke-first live_location privacy), so an invoker-rights read fails with permission denied before any row filter. The boundary is re-asserted in the view WHERE clause and locked by validate_service_dispatch_isolation.py.';

comment on view public.v_service_job_tracking is
  'The ONLY read path to a provider live_location, and only for that job''s parties while it is active. security_invoker stays FALSE for the same reason as the broadcast feed - it reads the column-revoked service_providers. Locked by validate_service_geo_privacy.py (a stranger reads 0 rows).';

COMMIT;
