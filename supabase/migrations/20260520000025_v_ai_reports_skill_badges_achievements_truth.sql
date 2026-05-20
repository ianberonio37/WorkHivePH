-- ─── Turn 5: 3 more canonical wrappers ─────────────────────────────────────
-- Continues the canonical-drift flywheel (turn 5 / 2026-05-20). All three
-- tables had 3+ raw reads at baseline and live across multiple surfaces.

-- ── v_ai_reports_truth ──────────────────────────────────────────────────────
-- AI agent output cache. Multiple consumers read by report_type (pm_overdue /
-- failure_digest / shift_handover / predictive); the bridge exposes type
-- flags + freshness (hours since generation) so consumers can drop the
-- `(now - generated_at) < threshold` scatter.
DROP VIEW IF EXISTS public.v_ai_reports_truth;
CREATE VIEW public.v_ai_reports_truth AS
SELECT
  r.id,
  r.hive_id,
  r.report_type,
  r.generated_at,
  r.report_json,
  r.summary,
  r.created_at,
  -- Derived freshness
  EXTRACT(EPOCH FROM (now() - r.generated_at))/3600.0           AS hours_since_generated,
  (r.generated_at >= now() - interval '24 hours')              AS fresh_24h,
  (r.generated_at >= now() - interval '8 hours')               AS fresh_8h,
  -- Derived type flags
  (r.report_type = 'pm_overdue')      AS is_pm_overdue,
  (r.report_type = 'failure_digest')  AS is_failure_digest,
  (r.report_type = 'shift_handover')  AS is_shift_handover,
  (r.report_type = 'predictive')      AS is_predictive
FROM public.ai_reports r;
GRANT SELECT ON public.v_ai_reports_truth TO anon, authenticated;
COMMENT ON VIEW public.v_ai_reports_truth IS
  'Canonical ai_reports reader. Per-report + freshness derivatives (hours_since_generated, fresh_24h, fresh_8h) + 4 type flags.';

-- ── v_skill_badges_truth ────────────────────────────────────────────────────
-- Bridges to worker_profiles for current display_name; derives is_recent
-- (earned within 30 days) and badge-tier-text mapping (1=Trainee … 5=Master).
DROP VIEW IF EXISTS public.v_skill_badges_truth;
CREATE VIEW public.v_skill_badges_truth AS
SELECT
  b.id,
  b.worker_name,
  b.auth_uid,
  b.discipline,
  b.level,
  b.exam_score,
  b.earned_at,
  -- Bridge to worker_profiles for live display_name (workers may have
  -- renamed since the badge was earned)
  wp.display_name           AS worker_display_name,
  wp.email                  AS worker_email,
  -- Derived
  CASE b.level
    WHEN 1 THEN 'Trainee'
    WHEN 2 THEN 'Operator'
    WHEN 3 THEN 'Technician'
    WHEN 4 THEN 'Specialist'
    WHEN 5 THEN 'Master'
    ELSE        'Unknown'
  END                        AS level_label,
  (b.earned_at >= now() - interval '30 days') AS earned_recent
FROM public.skill_badges b
LEFT JOIN public.worker_profiles wp ON wp.display_name = b.worker_name;
GRANT SELECT ON public.v_skill_badges_truth TO anon, authenticated;
COMMENT ON VIEW public.v_skill_badges_truth IS
  'Canonical skill_badges reader. Worker bridge (display_name/email) + level_label trichotomy + earned_recent flag.';

-- ── v_worker_achievements_truth ─────────────────────────────────────────────
-- Bridges to achievement_definitions for the definition (name, levels,
-- description) + worker_profiles for display_name; derives next-level XP
-- progress so consumers don't re-implement the math.
-- 2026-05-20: my turn-5 v_worker_achievements_truth assumed xp_per_level
-- existed on achievement_definitions; the table from 20260508000002 has
-- only max_level. ALTER TABLE adds xp_per_level with a sane default so
-- the view's progress math doesn't divide by zero.
ALTER TABLE IF EXISTS public.achievement_definitions
  ADD COLUMN IF NOT EXISTS xp_per_level int NOT NULL DEFAULT 100;
DROP VIEW IF EXISTS public.v_worker_achievements_truth;
CREATE VIEW public.v_worker_achievements_truth AS
SELECT
  wa.id,
  wa.auth_uid,
  wa.worker_name,
  wa.achievement_id,
  wa.current_level,
  wa.xp_total,
  wa.last_action_at,
  -- Bridge: definition (name, max level, etc.)
  ad.name              AS achievement_name,
  ad.description       AS achievement_description,
  ad.xp_per_level      AS xp_per_level,
  ad.max_level         AS max_level,
  -- Bridge: worker display name (live, not snapshot)
  wp.display_name      AS worker_display_name,
  -- Derived flags + progress math
  (wa.current_level >= ad.max_level)                              AS is_maxed,
  CASE WHEN ad.xp_per_level > 0
       THEN (wa.xp_total - (wa.current_level * ad.xp_per_level))::int
       ELSE 0
  END                                                              AS xp_into_current_level,
  CASE WHEN ad.xp_per_level > 0 AND wa.current_level < ad.max_level
       THEN (((wa.current_level + 1) * ad.xp_per_level) - wa.xp_total)::int
       ELSE 0
  END                                                              AS xp_to_next_level,
  (wa.last_action_at >= now() - interval '7 days')                AS earned_last_7d
FROM public.worker_achievements wa
LEFT JOIN public.achievement_definitions ad ON ad.id = wa.achievement_id
LEFT JOIN public.worker_profiles wp ON wp.display_name = wa.worker_name;
GRANT SELECT ON public.v_worker_achievements_truth TO anon, authenticated;
COMMENT ON VIEW public.v_worker_achievements_truth IS
  'Canonical worker_achievements reader. Definition bridge (name/desc/xp_per_level/max_level) + worker bridge + xp-progress math (is_maxed, xp_into_current_level, xp_to_next_level) + earned_last_7d.';

-- ── Register all three ─────────────────────────────────────────────────────
INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES
  ('ai_reports_truth', 'view', 'v_ai_reports_truth', 'ai-engineer', 'realtime',
   'Canonical ai_reports reader. Per-report granularity + freshness derivatives + 4 type flags.',
   jsonb_build_object(
     'key', jsonb_build_array('id'), 'hive_scoped', true, 'soft_delete', false,
     'derived_columns', jsonb_build_array('hours_since_generated','fresh_24h','fresh_8h','is_pm_overdue','is_failure_digest','is_shift_handover','is_predictive')
   ),
   'Turn 5 TIER C gap-table sweep (2026-05-20). 3 raw reads at baseline.'),
  ('skill_badges_truth', 'view', 'v_skill_badges_truth', 'community', 'realtime',
   'Canonical skill_badges reader. Worker bridge + level_label + earned_recent.',
   jsonb_build_object(
     'key', jsonb_build_array('id'), 'hive_scoped', false, 'soft_delete', false,
     'bridge_columns',  jsonb_build_array('worker_display_name','worker_email'),
     'derived_columns', jsonb_build_array('level_label','earned_recent')
   ),
   'Turn 5 TIER C gap-table sweep (2026-05-20). 3 raw reads at baseline.'),
  ('worker_achievements_truth', 'view', 'v_worker_achievements_truth', 'community', 'realtime',
   'Canonical worker_achievements reader. Definition + worker bridges + xp-progress math.',
   jsonb_build_object(
     'key', jsonb_build_array('id'), 'hive_scoped', false, 'soft_delete', false,
     'bridge_columns',  jsonb_build_array('achievement_name','achievement_description','xp_per_level','max_level','worker_display_name'),
     'derived_columns', jsonb_build_array('is_maxed','xp_into_current_level','xp_to_next_level','earned_last_7d')
   ),
   'Turn 5 TIER C gap-table sweep (2026-05-20). 3 raw reads at baseline.')
ON CONFLICT (domain) DO UPDATE
  SET source_kind = EXCLUDED.source_kind, source_name = EXCLUDED.source_name,
      owner_skill = EXCLUDED.owner_skill, freshness = EXCLUDED.freshness,
      description = EXCLUDED.description, contract = EXCLUDED.contract,
      notes       = EXCLUDED.notes;
