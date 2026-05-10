-- ─── Status CHECK constraints — close 7 unconstrained-status findings ────────
--
-- validate_state_machine_integrity.py L3 surfaced 7 status columns across the
-- platform with no CHECK constraint listing the allowed values. Without the
-- CHECK, any string is accepted; case drift ('Done' vs 'done') and typos
-- ('Compleed') are silent. This migration locks each column down to the set
-- the codebase actually uses.
--
-- Audit (run before authoring each constraint):
--   SELECT DISTINCT status FROM <table>;
-- Findings (2026-05-10 local DB):
--   assets:                   {approved}                          (90 rows)
--   external_sync.status:     {} (table empty); STATUS_MAP normalizes to Open/Closed/Cancelled
--   external_sync.sync_status: {} (table empty); migration doc says active/deleted/error
--   failure_signature_alerts: {active}                            (161 rows)
--   hive_members:             {active}                            (15 rows; kicked also referenced in code)
--   inventory_items:          {approved}                          (81 rows)
--   logbook:                  {Open, Closed}                      (3700 rows; Resolved referenced in dayplanner.html)
--   pm_completions:           {done, skipped}                     (1614 rows)
--
-- Each constraint is wider than the live data to accept code paths that
-- exist but haven't been exercised in the local seed (e.g. asset rejection,
-- alert acknowledgment, member kick). Re-running the migration is safe —
-- DROP CONSTRAINT IF EXISTS first.

BEGIN;

-- assets — supervisor approval workflow (mirrors asset_nodes)
ALTER TABLE public.assets DROP CONSTRAINT IF EXISTS assets_status_check;
ALTER TABLE public.assets ADD  CONSTRAINT assets_status_check
  CHECK (status IN ('approved', 'pending', 'rejected'));

-- external_sync.status — canonical WorkHive status from STATUS_MAP normalization.
-- Unmapped CMMS codes will fail the constraint, surfacing the gap so STATUS_MAP
-- can be extended (preferred over silent raw-code passthrough).
-- (PostgreSQL CHECK passes NULL automatically — `IS NULL OR` redundant.)
ALTER TABLE public.external_sync DROP CONSTRAINT IF EXISTS external_sync_status_check;
ALTER TABLE public.external_sync ADD  CONSTRAINT external_sync_status_check
  CHECK (status IN ('Open', 'Closed', 'Cancelled'));

-- external_sync.sync_status — bridge-row lifecycle. Adding 'failed' and 'success'
-- beyond the documented set since cmms-sync writes them on error/ok.
ALTER TABLE public.external_sync DROP CONSTRAINT IF EXISTS external_sync_sync_status_check;
ALTER TABLE public.external_sync ADD  CONSTRAINT external_sync_sync_status_check
  CHECK (sync_status IN ('active', 'deleted', 'error', 'failed', 'success'));

-- failure_signature_alerts — failure-signature-scan writes 'active'; columns
-- acknowledged_by/acknowledged_at suggest 'acknowledged'; 'expired' covers
-- the auto-expiry (alerts.expires_at < now()).
ALTER TABLE public.failure_signature_alerts DROP CONSTRAINT IF EXISTS failure_signature_alerts_status_check;
ALTER TABLE public.failure_signature_alerts ADD  CONSTRAINT failure_signature_alerts_status_check
  CHECK (status IN ('active', 'acknowledged', 'expired'));

-- hive_members — 'active' is the steady state; 'kicked' is set by supervisor
-- kick UI; loadMembers filters .neq('status', 'kicked') so the value is real.
ALTER TABLE public.hive_members DROP CONSTRAINT IF EXISTS hive_members_status_check;
ALTER TABLE public.hive_members ADD  CONSTRAINT hive_members_status_check
  CHECK (status IN ('active', 'kicked'));

-- inventory_items — supervisor approval workflow
ALTER TABLE public.inventory_items DROP CONSTRAINT IF EXISTS inventory_items_status_check;
ALTER TABLE public.inventory_items ADD  CONSTRAINT inventory_items_status_check
  CHECK (status IN ('approved', 'pending', 'rejected'));

-- logbook — Open / Closed are the dominant lifecycle; Resolved appears in
-- dayplanner.html filter (line 561) for legacy entries that some pages still
-- emit. Including it for back-compat; future cleanup could collapse to Open/Closed.
ALTER TABLE public.logbook DROP CONSTRAINT IF EXISTS logbook_status_check;
ALTER TABLE public.logbook ADD  CONSTRAINT logbook_status_check
  CHECK (status IN ('Open', 'Closed', 'Resolved'));

-- pm_completions — 'done' is the green path, 'skipped' is the worker-marks-NA path.
ALTER TABLE public.pm_completions DROP CONSTRAINT IF EXISTS pm_completions_status_check;
ALTER TABLE public.pm_completions ADD  CONSTRAINT pm_completions_status_check
  CHECK (status IN ('done', 'skipped'));

COMMIT;
