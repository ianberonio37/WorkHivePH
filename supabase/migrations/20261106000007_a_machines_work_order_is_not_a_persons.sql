-- ★A MACHINE'S WORK ORDER WAS WRITTEN UNDER A SUPERVISOR'S NAME, AND PAID THEM FOR IT (2026-11-06, GJ M9 J15: "the synced
-- work orders in the logbook").
--
-- cmms-webhook-receiver attributed every work order a CMMS pushed to "a worker": the hive's first supervisor found. The
-- logbook then read as if that supervisor had written it, and this trigger paid them 20 XP (more for a long entry) for
-- a record a machine sent. The receiver now writes the entry under the connection's own name ("CMMS: <connection>")
-- and marks its origin in sync_meta {source: "cmms", ...}; the XP trigger pays nobody for an entry so marked. Only the
-- guard at the top is new - the function is otherwise its current definition.

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
  -- a work order a CMMS pushed is a machine's record, not a person's work: nobody is paid for it (2026-11-06)
  IF coalesce(NEW.sync_meta->>'source', '') = 'cmms' THEN
    RETURN NEW;
  END IF;

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
