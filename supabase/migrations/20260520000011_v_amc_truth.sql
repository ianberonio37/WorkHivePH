-- v_amc_truth — canonical wrapper for AMC (Autonomous Maintenance Composer)
-- daily briefings. One row per (hive, shift_date) with the LATEST pending
-- brief surfaced for consumers; older briefs accessible via raw table.
--
-- Closes 2 gap reads identified by audit_calm_dashboard_canonical
-- (ops-home Today's One Thing AMC pending; alert-hub AMC briefing card).
--
-- Contract:
--   amc_id          briefing UUID
--   hive_id         scope
--   shift_date      Asia/Manila shift date
--   generated_at    when AMC composed the brief
--   status          'pending'|'approved'|'rejected'|'expired'
--   asset_count     # top assets in the brief (generated column from JSONB)
--   pm_count        # PMs due (generated)
--   parts_count     # parts to stage (generated)
--   summary         short narrative from brief.summary (extracted)
--   headline        action headline from brief.headline (extracted)
--   approved_by     supervisor who signed off (NULL if pending)
--   approved_at     sign-off timestamp
--   expires_at      auto-expiry (36h default)
--
-- Writes still target amc_briefings directly (amc-orchestrator edge fn).

BEGIN;

CREATE OR REPLACE VIEW public.v_amc_truth AS
SELECT DISTINCT ON (a.hive_id, a.shift_date)
  a.id                              AS amc_id,
  a.hive_id,
  a.shift_date,
  a.generated_at,
  a.status,
  a.asset_count,
  a.pm_count,
  a.parts_count,
  COALESCE(a.brief ->> 'summary',  a.brief ->> 'composer_summary', '')::text AS summary,
  COALESCE(a.brief ->> 'headline', a.brief ->> 'composer_headline', '')::text AS headline,
  a.approved_by,
  a.approved_at,
  a.expires_at,
  a.model_version
FROM public.amc_briefings a
ORDER BY a.hive_id, a.shift_date, a.generated_at DESC;

COMMENT ON VIEW public.v_amc_truth IS
  'Tier D canonical: latest AMC briefing per (hive, shift_date) with summary + headline extracted from the JSONB brief. Consumers (Today''s One Thing ranker, alert-hub AMC card) read this instead of amc_briefings directly.';

GRANT SELECT ON public.v_amc_truth TO anon, authenticated;

INSERT INTO public.canonical_sources (domain, source_kind, source_name, owner_skill, freshness, contract, description, registered_at)
VALUES (
  'amc_truth',
  'view',
  'v_amc_truth',
  'ai-engineer',
  'realtime',
  '{"columns":["amc_id","hive_id","shift_date","generated_at","status","asset_count","pm_count","parts_count","summary","headline","approved_by","approved_at","expires_at","model_version"]}'::jsonb,
  'Latest-per-shift AMC briefing canonical view. Closes 2 gap reads (ops-home Today ranker + alert-hub AMC card).',
  now()
)
ON CONFLICT (domain) DO UPDATE
  SET source_name = EXCLUDED.source_name,
      contract    = EXCLUDED.contract,
      description = EXCLUDED.description;

COMMIT;
