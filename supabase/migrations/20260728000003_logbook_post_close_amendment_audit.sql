-- ─────────────────────────────────────────────────────────────────────────────
-- Make a post-close amendment tamper-EVIDENT at the database, not just in the UI.
--
-- FOUND BY THE LB11 WALK (2026-07-28, LOGBOOK_DEEPWALK_EXPANSION_ROADMAP):
-- a Closed entry is fully mutable. Measured live: a signed-off entry's content was amended, and
-- the entry was then silently re-opened (status back to 'Open', closed_at nulled) by a direct
-- client write. Nothing recorded either, because the amendment audit row is written by the CLIENT
-- (writeAuditLog in logbook.html) and any write that does not go through that page skips it.
--
-- Client-side audit logging can always be bypassed. For an entry a technician has SIGNED OFF, and
-- which the DOLE/ISO export presents as the audit trail, "evident" has to mean the database
-- recorded it. Extension 3 of the PDDA arc claimed tamper-evidence; this is what makes it true.
--
-- SCOPE IS DELIBERATELY NARROW, to avoid duplicating the rows the client already writes:
-- this fires ONLY when the row was ALREADY Closed before the update -- a post-close amendment or a
-- re-open. Ordinary edits to an Open entry are untouched and stay client-logged, so the common
-- path gains no duplicate. A post-close amendment made through the UI will produce both rows; that
-- is the right trade, because the DB row is the one an auditor can trust and the client row
-- carries the richer context (parts added, category) that the trigger cannot see.
--
-- Note the actor: auth.uid() is resolved to a worker_name via hive_members so the entry reads like
-- the rest of the trail, falling back to the row's own worker_name, then to a literal marker rather
-- than a guess. A NULL actor would be worse than an honest 'unknown'.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.audit_logbook_post_close_amendment()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_actor text;
BEGIN
  -- Only rows that were already signed off. Everything else is an ordinary edit.
  IF COALESCE(OLD.status, '') <> 'Closed' THEN
    RETURN NEW;
  END IF;

  -- Ignore no-op updates (a re-save that changed nothing is not an amendment).
  IF NEW IS NOT DISTINCT FROM OLD THEN
    RETURN NEW;
  END IF;

  SELECT hm.worker_name INTO v_actor
    FROM public.hive_members hm
   WHERE hm.auth_uid = auth.uid()
   LIMIT 1;

  INSERT INTO public.hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta)
  VALUES (
    NEW.hive_id,
    COALESCE(v_actor, NEW.worker_name, 'unknown'),
    CASE WHEN COALESCE(NEW.status, '') <> 'Closed'
         THEN 'reopen_closed_logbook_entry'
         ELSE 'amend_closed_logbook_entry' END,
    'logbook',
    NEW.id,
    COALESCE(NEW.machine, '(no machine)'),
    jsonb_build_object(
      'prev_status',    OLD.status,
      'new_status',     NEW.status,
      'closed_at_was',  OLD.closed_at,
      'closed_at_now',  NEW.closed_at,
      'source',         'db_trigger'
    )
  );

  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_logbook_post_close_audit ON public.logbook;
CREATE TRIGGER trg_logbook_post_close_audit
  AFTER UPDATE ON public.logbook
  FOR EACH ROW
  EXECUTE FUNCTION public.audit_logbook_post_close_amendment();
