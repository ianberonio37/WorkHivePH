-- ★A LINKED CALCULATION NEVER SAID WHO LINKED IT (2026-11-06, GJ M9 J30: "the engineer's saved calculation is on the
-- project the supervisor reads", "the report management acts on").
--
-- The same gap as scope items (20261106000005), one table over: project_links records the label, the type and when, and
-- not who - so the supervisor's "Linked work" and the printed project report listed an engineer's calculation with no
-- name beside it. The report is what management acts on; a line in it that nobody stands behind is weaker evidence.
--
-- project_links gains linked_by, stamped by the server on insert from the caller's own profile name (never a client
-- value, never changed after); both surfaces say "linked by <name> · <when>".

BEGIN;

ALTER TABLE public.project_links ADD COLUMN IF NOT EXISTS linked_by text;

CREATE OR REPLACE FUNCTION public.tg_project_links_bind_linked_by()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE v_name text;
BEGIN
  IF TG_OP = 'UPDATE' THEN
    NEW.linked_by := OLD.linked_by;   -- who linked it never changes after
    RETURN NEW;
  END IF;
  IF auth.uid() IS NOT NULL THEN
    SELECT display_name INTO v_name FROM public.worker_profiles WHERE auth_uid = auth.uid() LIMIT 1;
    IF v_name IS NULL THEN
      SELECT worker_name INTO v_name FROM public.hive_members
       WHERE auth_uid = auth.uid() AND hive_id = NEW.hive_id AND status = 'active' LIMIT 1;
    END IF;
    NEW.linked_by := v_name;          -- always the caller's own name; a client-sent value is overwritten
  END IF;
  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_project_links_bind_linked_by ON public.project_links;
CREATE TRIGGER trg_project_links_bind_linked_by
  BEFORE INSERT OR UPDATE ON public.project_links
  FOR EACH ROW EXECUTE FUNCTION public.tg_project_links_bind_linked_by();

REVOKE ALL ON FUNCTION public.tg_project_links_bind_linked_by() FROM PUBLIC, anon, authenticated;

COMMIT;
