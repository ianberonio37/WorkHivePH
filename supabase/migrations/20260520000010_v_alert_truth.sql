-- v_alert_truth — canonical wrapper for active platform alerts.
--
-- Composite over failure_signature_alerts + anomaly_signals (the two
-- alert-class tables read raw by ops-home + alert-hub + hive). Closes
-- 3 gap reads identified by audit_calm_dashboard_canonical.
--
-- Contract:
--   alert_id        canonical id (UUID)
--   hive_id         scope
--   asset_id        nullable asset reference (uuid where available; else null)
--   machine         text machine name (always populated)
--   alert_kind      'signature' | 'anomaly'
--   severity        normalized to 'critical'|'high'|'medium'|'low'|'info'
--   title           short human title
--   detail          longer description
--   detected_at     when the signal fired
--   status          'active' | 'acknowledged' | 'expired'
--   evidence        JSONB grab-bag of supporting data
--
-- Surfaces opt in by reading v_alert_truth instead of either underlying
-- table directly. Writes still target the underlying tables (alert
-- generation is an edge fn responsibility).

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
  fsa.rule_id                     AS rule_id,        -- signature rule slug (consumers like hive.html label by this)
  fsa.category                    AS category,
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
  NULL::text                      AS rule_id,        -- anomaly_signals have no rule_id; composite-score driven
  NULL::text                      AS category,
  ans.computed_at                 AS detected_at,
  ans.status,
  ans.evidence
FROM public.anomaly_signals ans
WHERE ans.status IN ('active', 'acknowledged');

COMMENT ON VIEW public.v_alert_truth IS
  'Tier D canonical: unified active-alerts feed over failure_signature_alerts + anomaly_signals. Normalizes severity vocabulary, exposes asset_id where available, and emits alert_kind so consumers can branch render.';

GRANT SELECT ON public.v_alert_truth TO anon, authenticated;

INSERT INTO public.canonical_sources (domain, source_kind, source_name, owner_skill, freshness, contract, description, registered_at)
VALUES (
  'alert_truth',
  'view',
  'v_alert_truth',
  'notifications',
  'realtime',
  '{"columns":["alert_id","hive_id","asset_id","machine","alert_kind","severity","title","detail","rule_id","category","detected_at","status","evidence"]}'::jsonb,
  'Unified active-alerts canonical view over failure_signature_alerts + anomaly_signals. Closes 3 gap reads on ops-home / alert-hub / hive.',
  now()
)
ON CONFLICT (domain) DO UPDATE
  SET source_name = EXCLUDED.source_name,
      contract    = EXCLUDED.contract,
      description = EXCLUDED.description;

COMMIT;
