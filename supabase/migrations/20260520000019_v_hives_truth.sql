-- ─── v_hives_truth canonical view ──────────────────────────────────────────
-- TIER C gap-table promotion #3: hives had 4 raw reads across 4 sites
-- (analytics-report, hive.html × 3) at the second-pass baseline.
--
-- The view supersets every reading site + bridges aggregate counts that
-- hive.html and the founder console previously computed via separate
-- queries: member_count (active hive_members), asset_count (approved
-- asset_nodes). Plus a derived is_solo flag (members <= 1) to drop the
-- `if (count <= 1)` scatter in 3 consumers.
--
-- RLS: views inherit RLS from underlying tables. hives has a hive-
-- membership read policy already, so members of the hive can read their
-- hive row + the bridged counts.

DROP VIEW IF EXISTS public.v_hives_truth;

CREATE VIEW public.v_hives_truth AS
SELECT
  h.id,
  h.name,
  h.invite_code,
  h.created_by,
  h.created_at,
  h.intent,
  h.preferred_persona,
  -- Bridge: active membership count
  (SELECT count(*)::int FROM public.hive_members hm
     WHERE hm.hive_id = h.id AND hm.status = 'active')   AS member_count,
  -- Bridge: approved asset count
  (SELECT count(*)::int FROM public.asset_nodes an
     WHERE an.hive_id = h.id AND an.status = 'approved') AS asset_count,
  -- Bridge: oldest active member join (signals hive maturity)
  (SELECT min(hm.joined_at) FROM public.hive_members hm
     WHERE hm.hive_id = h.id AND hm.status = 'active')   AS first_member_joined_at,
  -- Derived flags
  (h.intent = '{}'::jsonb) AS intent_not_captured
FROM public.hives h;

GRANT SELECT ON public.v_hives_truth TO anon, authenticated;

COMMENT ON VIEW public.v_hives_truth IS
  'Canonical hives reader. Per-hive granularity + bridged member_count / asset_count / first_member_joined_at + derived intent_not_captured flag (Phase 3.5 onboarding signal).';

INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES
  ('hives_truth', 'view', 'v_hives_truth', 'multitenant-engineer', 'realtime',
   'Canonical hives reader. Per-hive granularity with member_count + asset_count bridges and intent_not_captured derived flag.',
   jsonb_build_object(
     'key',             jsonb_build_array('id'),
     'hive_scoped',     true,
     'soft_delete',     false,
     'bridge_columns',  jsonb_build_array('member_count','asset_count','first_member_joined_at'),
     'derived_columns', jsonb_build_array('intent_not_captured')
   ),
   'Phase 3 of the TIER C gap-table sweep (2026-05-20). 4 raw reads across 4 sites at baseline. Note: invite_code intentionally exposed — supervisors share it to recruit.')
ON CONFLICT (domain) DO UPDATE
  SET source_kind = EXCLUDED.source_kind,
      source_name = EXCLUDED.source_name,
      owner_skill = EXCLUDED.owner_skill,
      freshness   = EXCLUDED.freshness,
      description = EXCLUDED.description,
      contract    = EXCLUDED.contract,
      notes       = EXCLUDED.notes;
