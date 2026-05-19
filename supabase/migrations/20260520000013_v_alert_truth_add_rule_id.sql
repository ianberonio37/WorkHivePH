-- Extend v_alert_truth with rule_id + category (failure_signature_alerts
-- branch only; the anomaly_signals branch has no rule kind so NULL there).
--
-- Why a follow-up migration instead of editing 20260520000010:
--   Migration immutability gate (validate_migration_immutability.py L1)
--   forbids editing a migration after its first commit. The original
--   contract is locked; column additions ship as new migrations.
--
-- CREATE OR REPLACE VIEW disallows column-order changes, so we DROP +
-- CREATE to slot rule_id between detail and detected_at. Postgres handles
-- the DROP cleanly because consumers see the column-name renames as
-- additive (existing columns still present, just two new ones).
--
-- Consumers that benefit:
--   hive.html pattern-alerts panel labels by rule_id
--   future predictive surfaces can group alerts by category

BEGIN;

DROP VIEW IF EXISTS public.v_alert_truth;

CREATE VIEW public.v_alert_truth AS
SELECT
  fsa.id                          AS alert_id,
  fsa.hive_id,
  NULL::uuid                      AS asset_id,
  fsa.machine,
  'signature'::text               AS alert_kind,
  CASE
    WHEN fsa.severity = 'critical' THEN 'critical'
    WHEN fsa.severity = 'warning'  THEN 'high'
    WHEN fsa.severity = 'info'     THEN 'low'
    ELSE COALESCE(fsa.severity, 'info')
  END                             AS severity,
  fsa.alert_title                 AS title,
  fsa.alert_detail                AS detail,
  fsa.rule_id                     AS rule_id,       -- NEW: signature rule slug (consumers label by this)
  fsa.category                    AS category,      -- NEW: signature category
  fsa.detected_at,
  fsa.status,
  fsa.evidence
FROM public.failure_signature_alerts fsa
WHERE fsa.status IN ('active', 'acknowledged')

UNION ALL

SELECT
  ans.id                          AS alert_id,
  ans.hive_id,
  ans.asset_node_id               AS asset_id,
  ans.machine,
  'anomaly'::text                 AS alert_kind,
  ans.severity,
  ('Anomaly: ' || ans.machine)::text AS title,
  (
    SELECT string_agg(reason::text, ' · ')
    FROM jsonb_array_elements_text(ans.top_reasons) reason
  )                               AS detail,
  NULL::text                      AS rule_id,       -- NEW: anomaly_signals have no rule_id
  NULL::text                      AS category,     -- NEW: same
  ans.computed_at                 AS detected_at,
  ans.status,
  ans.evidence
FROM public.anomaly_signals ans
WHERE ans.status IN ('active', 'acknowledged');

COMMENT ON VIEW public.v_alert_truth IS
  'Tier D canonical: unified active-alerts feed over failure_signature_alerts + anomaly_signals. Normalizes severity, exposes alert_kind + rule_id + category. Migration 20260520000013 added rule_id + category in column-order break (DROP + CREATE).';

GRANT SELECT ON public.v_alert_truth TO anon, authenticated;

-- Update the canonical_sources contract to advertise the new columns.
UPDATE public.canonical_sources
   SET contract = '{"columns":["alert_id","hive_id","asset_id","machine","alert_kind","severity","title","detail","rule_id","category","detected_at","status","evidence"]}'::jsonb
 WHERE domain = 'alert_truth';

COMMIT;
