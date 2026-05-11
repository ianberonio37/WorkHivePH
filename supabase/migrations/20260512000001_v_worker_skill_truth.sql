-- Canonical Sources Phase A.5: v_worker_skill_truth view.
--
-- Per (hive_id, worker_name, discipline): current level (max badge level),
-- badge count, last_earned_at, plus primary_skill from skill_profiles.
-- Replaces four readers that each computed worker skill state differently:
--   * skillmatrix.html (live max() over skill_badges per worker)
--   * shift-planner-orchestrator (reads skill_badges + skill_profiles directly)
--   * analytics-orchestrator (rolls up skill coverage per discipline)
--   * AMC's Crew-Builder sub-agent (needs "best match for discipline X" lookup)
--
-- Workers with zero badges still appear (LEFT JOIN), with NULL discipline +
-- NULL current_level. Crew-Builder filters those out when matching.
--
-- Solo-mode workers (no hive) are NOT in this view because the AMC use case
-- is hive-scoped (a hive supervisor approving a daily brief for the team).
-- skillmatrix.html keeps reading skill_badges directly for solo mode.
--
-- Skills consulted:
--   maintenance-expert (level/discipline taxonomy)
--   multitenant-engineer (hive-membership-join pattern, not raw hive_id)
--   data-engineer (CTE for clarity, LEFT JOIN preserves zero-badge workers)
--   architect (canonical view + registry pattern, GRANT to anon + authenticated)

BEGIN;

CREATE OR REPLACE VIEW public.v_worker_skill_truth AS
WITH worker_in_hive AS (
  -- One row per (hive, worker). Only active members.
  SELECT
    hm.hive_id,
    hm.worker_name,
    hm.role,
    hm.auth_uid,
    hm.joined_at
  FROM public.hive_members hm
  WHERE hm.status = 'active'
),
levels_per_discipline AS (
  -- Per worker per discipline: highest level, count of badges, last earned.
  -- The level model is 1..5 with higher = more capable.
  SELECT
    worker_name,
    discipline,
    MAX(level)       AS current_level,
    COUNT(*)         AS badge_count,
    MAX(earned_at)   AS last_earned_at
  FROM public.skill_badges
  WHERE level BETWEEN 1 AND 5
  GROUP BY worker_name, discipline
)
SELECT
  wih.hive_id,
  wih.worker_name,
  wih.role,
  wih.auth_uid,
  wih.joined_at,
  sp.primary_skill,
  lpd.discipline,
  lpd.current_level,
  lpd.badge_count,
  lpd.last_earned_at
FROM worker_in_hive wih
LEFT JOIN public.skill_profiles sp
       ON sp.worker_name = wih.worker_name
LEFT JOIN levels_per_discipline lpd
       ON lpd.worker_name = wih.worker_name;

COMMENT ON VIEW public.v_worker_skill_truth IS
  'Canonical worker skill state per (hive_id, worker_name, discipline). Replaces 4-way scatter across skillmatrix.html, shift-planner-orchestrator, analytics-orchestrator, and AMC Crew-Builder. Registered in canonical_sources as domain=worker_skill_truth.';

GRANT SELECT ON public.v_worker_skill_truth TO anon, authenticated;

-- Register the truth.
INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES (
  'worker_skill_truth',
  'view',
  'v_worker_skill_truth',
  'maintenance-expert',
  'realtime',
  'Per (hive_id, worker_name, discipline): current_level (max badge), badge_count, last_earned_at, primary_skill. Source of truth for skill matrix, shift planner, analytics roll-ups, and AMC Crew-Builder assignment.',
  jsonb_build_object(
    'key', jsonb_build_array('hive_id', 'worker_name', 'discipline'),
    'hive_scoped', true,
    'level_range', jsonb_build_array(1, 5),
    'discipline_examples', jsonb_build_array(
      'electrical','mechanical','instrumentation','hvac','utilities','civil'
    ),
    'zero_badge_workers_present', true,
    'compose_pattern', 'For AMC Crew-Builder: filter WHERE discipline = ''X'' AND current_level >= 2 ORDER BY current_level DESC, last_earned_at DESC LIMIT 3'
  ),
  'Phase A.5 contract. Workers without badges appear with NULL discipline + NULL current_level (LEFT JOIN). Solo-mode workers (no hive_members row) are excluded by design - skillmatrix.html still reads skill_badges directly for that case.'
)
ON CONFLICT (domain) DO UPDATE
  SET source_kind   = EXCLUDED.source_kind,
      source_name   = EXCLUDED.source_name,
      owner_skill   = EXCLUDED.owner_skill,
      freshness     = EXCLUDED.freshness,
      description   = EXCLUDED.description,
      contract      = EXCLUDED.contract,
      notes         = EXCLUDED.notes,
      registered_at = now();

COMMIT;
