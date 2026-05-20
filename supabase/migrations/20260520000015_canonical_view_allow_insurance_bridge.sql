-- canonical-view-allow: v_insurance_bridge_truth
--
-- Declared in 20260513000007_phase6_industry_defining.sql but never read
-- by an in-app consumer. Reachability spec
-- (tests/journey-canonical-view-reachability.spec.ts) requires every
-- canonical view to have either ≥1 consumer or an `canonical-view-allow`
-- marker; this migration carries the marker per Phase 6 doctrine:
--
--   v_insurance_bridge_truth is a provisional underwriter-facing
--   composite (HRS + adoption_risk + anomaly load). Partner integration
--   is gated on actuarial review per the Phase 6 charter; no in-app
--   consumer ships until that review lands. Until then, the view's
--   only reader is the signed-export path (export-hive-data edge fn).
--
-- This is a documentation-only migration. No DDL, no DML, no policy.
-- It exists so the marker lives in the migrations folder where the
-- reachability spec scans.

DO $$ BEGIN
  RAISE NOTICE 'canonical-view-allow: v_insurance_bridge_truth — provisional partner-facing view, no in-app consumer by design (Phase 6 actuarial gate).';
END $$;
