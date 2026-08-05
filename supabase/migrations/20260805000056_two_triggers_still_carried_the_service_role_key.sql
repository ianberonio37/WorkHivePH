-- TWO TRIGGERS STILL CARRIED THE SERVICE-ROLE KEY IN THEIR OWN DEFINITION.
--
-- The 2026-07-31 embedding-outbox spine replaced the fire-and-forget webhook on `logbook`: it dropped
-- the `embed-logbook` trigger, attached `trg_embed_outbox_logbook`, and moved the work to a queue that
-- carries no secret and rolls back with the user's transaction. It converted ONE of the three surfaces.
--
-- `embed-pm-completions` and `embed-skill-badges` were never dropped by any migration — only the
-- baseline creates them — and both are still attached today. Each is a
-- `supabase_functions.http_request` trigger whose arguments hard-code the production URL and a
-- `service_role` JWT, stored verbatim in the trigger definition. Two consequences:
--
--   1. THE KEY CANNOT BE ROTATED WITHOUT BREAKING THEM. That is the wrong way round: a credential
--      should be rotatable without a schema change, and a trigger definition is a poor place to keep
--      one — it is readable by anything that can inspect the catalog, and it travels in every dump.
--   2. LOCALLY THEY POST TO PRODUCTION. Every insert into pm_completions or skill_badges on a
--      developer's machine fires a POST at the live project with the live key. That exact shape has
--      been found here before; it was fixed for logbook and the siblings were left behind.
--
-- The sibling surfaces were already registered by 20260731000003, and the `embed-entry` relay already
-- branches on all three tables (logbook / skill_badges / pm_completions), so the destination has been
-- ready the whole time — only the wiring stayed on the old path. This attaches the same
-- registry-driven `enqueue_for_embedding()` trigger the spine wrote, and ACTIVATES the two registry
-- rows so embedding continues rather than silently stopping the moment the old triggers go.
--
-- Local-only note: dropping these also ends the accidental local-to-production POSTs immediately,
-- before the key is rotated.

BEGIN;

-- ── pm_completions ─────────────────────────────────────────────────────────────────────────────────
DROP TRIGGER IF EXISTS "embed-pm-completions"          ON public.pm_completions;
DROP TRIGGER IF EXISTS trg_embed_outbox_pm_completions ON public.pm_completions;
CREATE TRIGGER trg_embed_outbox_pm_completions
  AFTER INSERT OR UPDATE ON public.pm_completions
  FOR EACH ROW EXECUTE FUNCTION public.enqueue_for_embedding();

-- ── skill_badges ───────────────────────────────────────────────────────────────────────────────────
DROP TRIGGER IF EXISTS "embed-skill-badges"          ON public.skill_badges;
DROP TRIGGER IF EXISTS trg_embed_outbox_skill_badges ON public.skill_badges;
CREATE TRIGGER trg_embed_outbox_skill_badges
  AFTER INSERT OR UPDATE ON public.skill_badges
  FOR EACH ROW EXECUTE FUNCTION public.enqueue_for_embedding();

-- Switch the surfaces on. `enqueue_for_embedding()` returns without enqueuing while a registry row is
-- inactive, so leaving these false would silently retire embedding for both surfaces instead of
-- migrating it — a quiet capability loss dressed as a security fix.
UPDATE public.embedding_registry SET active = true
 WHERE source_table IN ('pm_completions', 'skill_badges');

-- ── REFUSE TO COMMIT IF A SECRET SURVIVES IN ANY TRIGGER DEFINITION ────────────────────────────────
-- The point of this migration is that no trigger holds a credential. Asserting it directly is what
-- makes that a fact rather than an intention: a later migration re-creating one of these the old way
-- fails here instead of quietly restoring the exposure.
DO $$
DECLARE
  v_leaky text;
  v_wired int;
BEGIN
  SELECT string_agg(t.tgname, ', ')
    INTO v_leaky
    FROM pg_trigger t
   WHERE NOT t.tgisinternal
     AND pg_get_triggerdef(t.oid) ~ 'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{20,}';
  IF v_leaky IS NOT NULL THEN
    RAISE EXCEPTION 'a trigger definition still carries a JWT: %', v_leaky;
  END IF;

  SELECT count(*) INTO v_wired
    FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
   WHERE NOT t.tgisinternal
     AND c.relname IN ('pm_completions', 'skill_badges')
     AND t.tgname LIKE 'trg_embed_outbox_%';
  IF v_wired <> 2 THEN
    RAISE EXCEPTION 'expected both surfaces on the outbox path, found % trigger(s)', v_wired;
  END IF;

  RAISE NOTICE 'no trigger carries a credential; pm_completions and skill_badges are on the outbox';
END $$;

COMMIT;
