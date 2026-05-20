-- ─── v_community_posts_truth canonical view ─────────────────────────────────
-- TIER C gap-table promotion #2: community_posts had 8 raw reads across 3
-- consumers (community.html, public-feed.html, journey-community.spec.ts) at
-- baseline. validate_user_facing_kpi_canonical.py flagged it as the #2 gap-
-- table candidate on 2026-05-20.
--
-- The view supersets every reading site's column set AND bridges to the
-- `hives` table for hive_name (consumers currently inline a `hives(name)`
-- relationship select which the canonical-allow / drift miner can't reason
-- about). Two derived flags (is_deleted, is_edited) so soft-delete callers
-- can drop `.is('deleted_at', null)` boilerplate.
--
-- RLS: inherits from community_posts (hive-membership read policy + public
-- flag exposure for cross-hive feed). No extra policy.

DROP VIEW IF EXISTS public.v_community_posts_truth;

CREATE VIEW public.v_community_posts_truth AS
SELECT
  p.id,
  p.hive_id,
  p.author_name,
  p.auth_uid,
  p.content,
  p.category,
  p.pinned,
  p.flagged,
  p.public,
  p.created_at,
  p.edited_at,
  p.mentions,
  p.deleted_at,
  -- Bridge to hives for hive_name. Consumers inline `hives(name)` via
  -- PostgREST relationship today which works but bypasses canonical
  -- registration; the bridged column is the registered path.
  h.name AS hive_name,
  -- Derived flags drop is/.is('deleted_at', null) scatter
  (p.deleted_at IS NOT NULL) AS is_deleted,
  (p.edited_at  IS NOT NULL) AS is_edited
FROM public.community_posts p
LEFT JOIN public.hives h ON h.id = p.hive_id;

GRANT SELECT ON public.v_community_posts_truth TO anon, authenticated;

COMMENT ON VIEW public.v_community_posts_truth IS
  'Canonical community_posts reader. Supersets every consumer column + bridges to hives for hive_name. Derived is_deleted/is_edited flags drop soft-delete scatter.';

-- ─── Register in canonical_sources ───────────────────────────────────────────

INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES
  ('community_posts_truth', 'view', 'v_community_posts_truth', 'community', 'realtime',
   'Canonical community_posts reader. Per-post granularity with hives bridge (hive_name) and derived is_deleted/is_edited flags.',
   jsonb_build_object(
     'key',             jsonb_build_array('id'),
     'hive_scoped',     true,
     'soft_delete',     'deleted_at',
     'bridge_columns',  jsonb_build_array('hive_name'),
     'derived_columns', jsonb_build_array('is_deleted','is_edited')
   ),
   'Phase 2 of the TIER C gap-table sweep (2026-05-20). 8 raw reads across 3 consumers at baseline. Note: community_thread is already registered in canonical_sources as the underlying-table entry; this new entry registers the canonical READER view.')
ON CONFLICT (domain) DO UPDATE
  SET source_kind  = EXCLUDED.source_kind,
      source_name  = EXCLUDED.source_name,
      owner_skill  = EXCLUDED.owner_skill,
      freshness    = EXCLUDED.freshness,
      description  = EXCLUDED.description,
      contract     = EXCLUDED.contract,
      notes        = EXCLUDED.notes;
