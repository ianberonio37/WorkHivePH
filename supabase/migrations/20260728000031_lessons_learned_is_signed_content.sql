-- ─────────────────────────────────────────────────────────────────────────────
-- Lessons-learned is text on a SIGNED document. Any member could write it, on every project at once.
--
-- FOUND BY THE PJ14 WALK (2026-07-28), on the second persona — the shallow-W guard again refusing to
-- credit a journey on one, and again being the reason the defect surfaced.
--
-- `projects.meta` is an unstructured jsonb grab-bag, writable by any active member through the
-- table's single PERMISSIVE FOR ALL policy. Probed live as an ordinary worker, one statement:
--
--     UPDATE projects SET meta = jsonb_build_object(
--       'lessons_learned', 'worker-written sign-off text',
--       '_ai_generated_lessons', true)
--     WHERE hive_id = <mine>            ->  ACCEPTED, on EVERY project in the hive
--
-- WHY THIS IS NOT JUST ANOTHER FIELD. meta.lessons_learned is rendered on project-report.html, the
-- printable document whose own footer reads "By signing below, the parties acknowledge that the
-- scope items in §2 have been..." — so it is content on a document people sign. And the same write
-- forged `_ai_generated_lessons`, the badge that tells a reader "🤖 AI-drafted: supervisor edit
-- before sign-off recommended", which is exactly the provenance signal a reviewer would rely on.
--
-- Neither button is role-gated either (aiDraftLessons / saveLessons carry no isSupervisor check,
-- unlike Acknowledge which does), so this is reachable from the UI and not only from the API.
--
-- WHAT THIS GUARD DOES, and what it deliberately does NOT do:
--   * only a supervisor may CHANGE meta.lessons_learned — it is sign-off content
--   * every OTHER key in meta stays writable by any member, because meta is a genuine grab-bag
--     (wizard state, flags, UI preferences) and locking the whole column would break unrelated
--     writes that have nothing to do with sign-off
--   * the AI badge is NOT validated here. It is set client-side, so the database cannot tell a
--     truthful badge from a forged one — the honest fix is for the orchestrator to stamp it
--     server-side, and that is recorded as open rather than papered over with a check that would
--     only catch the careless case.
--
-- service_role keeps its reach (auth.uid() IS NULL), as everywhere else in these arcs.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.guard_lessons_learned_is_supervisor()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_old text := NULLIF(OLD.meta ->> 'lessons_learned', '');
  v_new text := NULLIF(NEW.meta ->> 'lessons_learned', '');
  v_is_sup boolean;
BEGIN
  IF auth.uid() IS NULL THEN
    RETURN NEW;                                   -- service_role / seeders / migrations
  END IF;

  -- Untouched? Then this is some other edit and none of this trigger's business.
  IF v_old IS NOT DISTINCT FROM v_new THEN
    RETURN NEW;
  END IF;

  SELECT EXISTS (
    SELECT 1 FROM public.hive_members hm
     WHERE hm.hive_id = NEW.hive_id AND hm.auth_uid = auth.uid()
       AND hm.status = 'active' AND hm.role = 'supervisor'
  ) INTO v_is_sup;

  IF NOT v_is_sup THEN
    RAISE EXCEPTION 'Lessons-learned appears on the signed project report, so only a supervisor of '
                    'this hive can change it (%).', COALESCE(NEW.project_code, OLD.project_code)
      USING ERRCODE = 'insufficient_privilege';
  END IF;

  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_lessons_learned_supervisor ON public.projects;
CREATE TRIGGER trg_lessons_learned_supervisor
  BEFORE UPDATE ON public.projects
  FOR EACH ROW
  EXECUTE FUNCTION public.guard_lessons_learned_is_supervisor();

COMMENT ON FUNCTION public.guard_lessons_learned_is_supervisor() IS
  'Only a supervisor may change meta.lessons_learned — it is rendered on the printable project '
  'report that parties sign. Before this, any active member could set it (and forge the AI-drafted '
  'badge alongside it) on every project in the hive in a single statement. Other meta keys stay '
  'freely writable; meta is a genuine grab-bag and locking the column would break unrelated writes. '
  'PJ14/PJK1, 2026-07-28.';
