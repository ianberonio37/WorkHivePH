-- Persona Contract Phase 6 — hive-level companion persona for autonomous
-- briefings (AMC). The AMC orchestrator runs unattended via pg_cron, so it
-- has no per-worker context to derive a persona from. Hives pick a single
-- "voice" that signs every shift brief for the whole crew.
--
-- Worker-level preference still wins on interactive surfaces (voice-journal,
-- floating-AI, assistant, asset-brain). This column only feeds AMC.
--
-- See WORKHIVE_PERSONA_CONTRACT.md + supabase/functions/_shared/persona.ts.

ALTER TABLE public.hives
  ADD COLUMN IF NOT EXISTS preferred_persona text NOT NULL DEFAULT 'james'
    CHECK (preferred_persona IN ('james', 'rosa'));

COMMENT ON COLUMN public.hives.preferred_persona IS
  'Persona Contract Phase 6: companion voice (james or rosa) that signs '
  'AMC briefings for this hive. Default james. Workers can still override '
  'on their own interactive surfaces via worker_profiles.preferred_persona.';
