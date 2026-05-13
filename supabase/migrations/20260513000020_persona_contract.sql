-- Persona Contract Foundation: worker_profiles.preferred_persona + view passthrough
--
-- Adds an account-level persona preference so every conversational AI
-- surface (voice-journal, floating-AI, assistant, AMC briefing footer)
-- can read the same source of truth. The worker picks James or Rosa once
-- and gets a consistent companion across pages.
--
-- See: WORKHIVE_PERSONA_CONTRACT.md
--
-- Skills consulted:
--   architect      (one column, CHECK-constrained, default value)
--   data-engineer  (view passthrough, no analytics impact)
--   ai-engineer    (downstream agents read this in their system prompt build)
--   multitenant-engineer (per-account preference, not per-hive)

BEGIN;

-- 1. Add the column to worker_profiles, with a default + CHECK constraint
ALTER TABLE public.worker_profiles
  ADD COLUMN IF NOT EXISTS preferred_persona text NOT NULL DEFAULT 'james'
    CHECK (preferred_persona IN ('james','rosa'));

COMMENT ON COLUMN public.worker_profiles.preferred_persona IS
  'Per-account conversational AI persona. james | rosa. Drives tone + name across voice-journal, floating-AI, assistant, AMC briefing signature. See WORKHIVE_PERSONA_CONTRACT.md.';

-- 2. Expose via the canonical worker view
DROP VIEW IF EXISTS public.v_worker_truth;
CREATE VIEW public.v_worker_truth AS
SELECT
  wp.auth_uid,
  wp.username,
  wp.display_name              AS worker_name,
  wp.email,
  wp.preferred_persona,
  wp.created_at                AS registered_at,
  hm.hive_id,
  hm.role,
  hm.joined_at                 AS hive_joined_at,
  hm.status                    AS hive_status,
  (hm.hive_id IS NULL)         AS is_solo,
  (SELECT count(*) FROM public.hive_members hm2
     WHERE hm2.worker_name = wp.display_name AND hm2.status = 'active') AS active_hive_count
FROM public.worker_profiles wp
LEFT JOIN public.hive_members hm
       ON hm.worker_name = wp.display_name
      AND hm.status      = 'active';

COMMENT ON VIEW public.v_worker_truth IS
  'Canonical worker identity + preferred_persona. Replaces direct worker_profiles + hive_members joins. preferred_persona feeds every conversational AI surface per WORKHIVE_PERSONA_CONTRACT.md.';

GRANT SELECT ON public.v_worker_truth TO anon, authenticated;

COMMIT;
