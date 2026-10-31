-- HS L5 (2026-10-30, the hive at thirty - the third clause of "a member who has left"): a departed member's OPEN logbook
-- entry could never be closed. The logbook's only UPDATE policy is the author's (auth_uid = auth.uid()), so once Rodel
-- Ignacio left, the jobs he had opened stayed Open on every board, in every open-jobs count and in the CMMS sync's
-- conflict list ("only its author can change it") - for ever, with nobody able to act on them.
-- Now: an ACTIVE supervisor of the entry's hive may close such an entry, or assign it to an active member of the hive -
-- and nothing else. The entry stays his (worker_name and auth_uid are untouched: he raised it and did that work), so
-- the trail tells the truth about who did what; the close audit triggers record the supervisor who closed it.
--   * WHICH rows: status 'Open', not in the trash, whose author is not an active member of the entry's hive.
--   * WHAT may change: status Open -> Closed, closed_at, action, root_cause, root_cause_note, wo_state, wo_assigned_to
--     (an active member's name), updated_at. Any other column changed by someone who is not the author is refused.
--   * The author's own updates are untouched - the guard steps aside for them and for the service role.

DROP POLICY IF EXISTS logbook_update_departed_open ON public.logbook;
CREATE POLICY logbook_update_departed_open ON public.logbook AS PERMISSIVE FOR UPDATE TO authenticated
  USING ((( SELECT auth.uid() AS uid) IS NOT NULL)
     AND (hive_id IN ( SELECT public.user_supervisor_hive_ids() AS user_supervisor_hive_ids))
     AND (status = 'Open'::text)
     AND (deleted_at IS NULL)
     AND (auth_uid IS NOT NULL)
     AND (NOT EXISTS ( SELECT 1 FROM public.hive_members hm
                        WHERE hm.hive_id = logbook.hive_id AND hm.auth_uid = logbook.auth_uid AND hm.status = 'active'::text)))
  WITH CHECK (hive_id IN ( SELECT public.user_supervisor_hive_ids() AS user_supervisor_hive_ids));

CREATE OR REPLACE FUNCTION public.guard_departed_entry_takeover()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE
  allowed text[] := ARRAY['status', 'closed_at', 'action', 'root_cause', 'root_cause_note', 'wo_state', 'wo_assigned_to', 'updated_at'];
  moved text;
BEGIN
  -- the author, and the platform acting for itself, are not this guard's business
  IF auth.uid() IS NULL OR OLD.auth_uid IS NOT DISTINCT FROM auth.uid() THEN
    RETURN NEW;
  END IF;
  SELECT string_agg(k, ', ') INTO moved
    FROM jsonb_each(to_jsonb(NEW)) n(k, v)
   WHERE NOT (k = ANY (allowed)) AND v IS DISTINCT FROM (to_jsonb(OLD) -> k);
  IF moved IS NOT NULL THEN
    RAISE EXCEPTION 'A supervisor can close or assign a departed member''s open job, not change it (%).', moved
      USING ERRCODE = '42501';
  END IF;
  IF NEW.status IS DISTINCT FROM OLD.status AND NEW.status <> 'Closed' THEN
    RAISE EXCEPTION 'A departed member''s open job can be closed, not set to %.', NEW.status USING ERRCODE = '42501';
  END IF;
  IF NEW.wo_assigned_to IS DISTINCT FROM OLD.wo_assigned_to AND NEW.wo_assigned_to IS NOT NULL
     AND NOT EXISTS (SELECT 1 FROM public.hive_members hm
                      WHERE hm.hive_id = NEW.hive_id AND hm.worker_name = NEW.wo_assigned_to AND hm.status = 'active') THEN
    RAISE EXCEPTION 'The job can be assigned only to an active member of this hive (% is not one).', NEW.wo_assigned_to
      USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END;
$function$;

REVOKE EXECUTE ON FUNCTION public.guard_departed_entry_takeover() FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS trg_guard_departed_entry_takeover ON public.logbook;
CREATE TRIGGER trg_guard_departed_entry_takeover BEFORE UPDATE ON public.logbook
  FOR EACH ROW EXECUTE FUNCTION public.guard_departed_entry_takeover();

-- Walked live, the first close of a departed member's job PAID HIM: trg_logbook_achievement_xp awarded Rodel Ignacio 50
-- 'logbook_close' XP for a job a supervisor closed after he had left. The close award is for the person who closes
-- their own job; it is now paid only when the closer is the entry's author (or the platform itself, e.g. a sync, as
-- before). A supervisor's take-over pays nobody. Everything else in the function is as it was.
CREATE OR REPLACE FUNCTION public.trg_logbook_achievement_xp()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_xp      int;
  v_content text;
BEGIN
  -- INSERT: entry submitted
  IF TG_OP = 'INSERT' THEN
    v_xp := 20;

    -- Knowledge Forger: combined text > 200 chars signals a detailed entry
    v_content := coalesce(NEW.problem, '') || coalesce(NEW.action, '') || coalesce(NEW.knowledge, '');
    IF char_length(v_content) > 200 THEN
      v_xp := v_xp + 20;
      PERFORM award_achievement_xp(
        NEW.worker_name, 'knowledge_forger', 20, 'detailed_entry', NEW.id);
    END IF;

    PERFORM award_achievement_xp(
      NEW.worker_name, 'wrench_chronicle', v_xp, 'logbook_submit', NEW.id);

    -- Safety Sentinel: safety-category entry
    IF NEW.category ILIKE '%safety%' THEN
      PERFORM award_achievement_xp(
        NEW.worker_name, 'safety_sentinel', 60, 'safety_entry', NEW.id);
    END IF;
  END IF;

  -- UPDATE: status transition to Closed - by the entry's own author (or the platform), never by someone taking it over
  IF TG_OP = 'UPDATE'
     AND NEW.status = 'Closed'
     AND (OLD.status IS DISTINCT FROM 'Closed')
     AND (auth.uid() IS NULL OR NEW.auth_uid IS NULL OR NEW.auth_uid = auth.uid()) THEN

    v_xp := 50;

    IF NEW.root_cause IS NOT NULL AND trim(NEW.root_cause) <> '' THEN
      v_xp := v_xp + 30;
    END IF;

    IF NEW.machine IS NOT NULL AND NEW.downtime_hours IS NOT NULL THEN
      v_xp := v_xp + 15;
    END IF;

    -- Closed within 24 h of submission
    IF NEW.closed_at IS NOT NULL AND NEW.created_at IS NOT NULL
       AND (NEW.closed_at - NEW.created_at) < interval '24 hours' THEN
      v_xp := v_xp + 25;
    END IF;

    PERFORM award_achievement_xp(
      NEW.worker_name, 'wrench_chronicle', v_xp, 'logbook_close', NEW.id);

    -- Failure Hunter: breakdown/corrective entry closed with root cause
    IF (NEW.maintenance_type ILIKE '%corrective%'
        OR NEW.maintenance_type ILIKE '%breakdown%'
        OR NEW.category        ILIKE '%breakdown%')
       AND NEW.root_cause IS NOT NULL
       AND trim(NEW.root_cause) <> '' THEN
      PERFORM award_achievement_xp(
        NEW.worker_name, 'failure_hunter', 100, 'breakdown_root_cause', NEW.id);
    END IF;
  END IF;

  RETURN NEW;
END;
$function$;
