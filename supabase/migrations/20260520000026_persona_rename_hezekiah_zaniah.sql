-- Persona Rename: james -> hezekiah, rosa -> zaniah  (2026-05-20)
--
-- Display-name + key swap requested by the workspace owner. The Azure
-- neural voices (en-PH-JamesNeural, en-PH-RosaNeural) and portrait
-- artwork stay the same — only the persona keys workers see and the DB
-- column values move.
--
-- This migration is idempotent: re-running it on an already-migrated row
-- is a no-op (UPDATE ... IN ('james','rosa') matches nothing, the CHECK
-- swap is guarded by IF EXISTS, the default is reset to the same value).
--
-- Surfaces affected at the SQL layer:
--   - worker_profiles.preferred_persona     (CHECK + DEFAULT + data)
--   - hives.preferred_persona               (CHECK + DEFAULT + data)
--   - tts_cache.persona                     (data only — text column)
--   - tts_quality_log.persona               (data only — text column)
--
-- v_worker_truth resolves columns by NAME at query time, so the
-- passthrough view returns the new values automatically — no view
-- recreate needed.
--
-- Application-layer fallback: persona.ts + wh-persona.js both ship a
-- one-month clampPersona() shim that maps any stale 'james'/'rosa'
-- payload (cached client, in-flight request) to the new key, so this
-- migration can land independently of a frontend cache cycle.
--
-- See: WORKHIVE_PERSONA_CONTRACT.md

BEGIN;

-- ── worker_profiles ─────────────────────────────────────────────────────

ALTER TABLE public.worker_profiles
  DROP CONSTRAINT IF EXISTS worker_profiles_preferred_persona_check;

UPDATE public.worker_profiles
   SET preferred_persona = CASE preferred_persona
                             WHEN 'james' THEN 'hezekiah'
                             WHEN 'rosa'  THEN 'zaniah'
                             ELSE preferred_persona
                           END
 WHERE preferred_persona IN ('james','rosa');

ALTER TABLE public.worker_profiles
  ALTER COLUMN preferred_persona SET DEFAULT 'zaniah';

ALTER TABLE public.worker_profiles
  ADD CONSTRAINT worker_profiles_preferred_persona_check
  CHECK (preferred_persona IN ('hezekiah','zaniah'));

COMMENT ON COLUMN public.worker_profiles.preferred_persona IS
  'Per-account conversational AI persona. hezekiah | zaniah. Drives tone + name across voice-journal, floating-AI, assistant, AMC briefing signature. See WORKHIVE_PERSONA_CONTRACT.md. Renamed 2026-05-20 from james/rosa.';

-- ── hives ───────────────────────────────────────────────────────────────

ALTER TABLE public.hives
  DROP CONSTRAINT IF EXISTS hives_preferred_persona_check;

UPDATE public.hives
   SET preferred_persona = CASE preferred_persona
                             WHEN 'james' THEN 'hezekiah'
                             WHEN 'rosa'  THEN 'zaniah'
                             ELSE preferred_persona
                           END
 WHERE preferred_persona IN ('james','rosa');

ALTER TABLE public.hives
  ALTER COLUMN preferred_persona SET DEFAULT 'zaniah';

ALTER TABLE public.hives
  ADD CONSTRAINT hives_preferred_persona_check
  CHECK (preferred_persona IN ('hezekiah','zaniah'));

COMMENT ON COLUMN public.hives.preferred_persona IS
  'Persona Contract Phase 6: companion voice (hezekiah or zaniah) that signs AMC briefings for this hive. Default zaniah. Workers can still override on their own interactive surfaces via worker_profiles.preferred_persona. Renamed 2026-05-20 from james/rosa.';

-- ── tts_cache / tts_quality_log (text columns, no CHECK) ────────────────
-- Update existing cached audio metadata so the persona label matches.
-- The cached MP3 bytes themselves are unchanged (same Azure voice IDs).

UPDATE public.tts_cache
   SET persona = CASE persona
                   WHEN 'james' THEN 'hezekiah'
                   WHEN 'rosa'  THEN 'zaniah'
                   ELSE persona
                 END
 WHERE persona IN ('james','rosa');

UPDATE public.tts_quality_log
   SET persona = CASE persona
                   WHEN 'james' THEN 'hezekiah'
                   WHEN 'rosa'  THEN 'zaniah'
                   ELSE persona
                 END
 WHERE persona IN ('james','rosa');

COMMIT;
