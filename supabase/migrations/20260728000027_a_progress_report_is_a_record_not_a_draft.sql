-- ─────────────────────────────────────────────────────────────────────────────
-- A worker could rewrite another worker's progress report, and acknowledge their own.
--
-- FOUND BY THE PJ6 WALK (2026-07-28, PROJECT_MANAGER_DEEPWALK_EXPANSION_ROADMAP). Three things,
-- all probed live as an ordinary worker:
--
--   1. REWROTE ANOTHER WORKER'S REPORT. Set pct_complete = 100 and replaced the notes on a log
--      filed by Leandro Marquez. The row still reads `reported_by = Leandro Marquez`, so the record
--      of what a technician said they did now says what somebody else wrote.
--
--   2. ACKNOWLEDGED SOMEONE ELSE'S REPORT. Acknowledgement is the supervisor's "I have seen this"
--      signal, and any active member could write it — ackLog() sets acknowledged_by = WORKER_NAME
--      with no role check, and wh_guard_supervisor_approval does not cover this table.
--
--   3. ACKNOWLEDGED THEIR OWN REPORT. `Bryan Garcia acked their OWN report as Bryan Garcia`. That is
--      the self-approval class AH3 closed for asset submissions, still open here: the one signal
--      that a supervisor reviewed the work can be manufactured by the person being reviewed.
--
-- LEGITIMATE CALLERS MEASURED FIRST, the discipline that has now saved four writes in two arcs:
-- there are exactly TWO write paths on this table in the whole codebase — the INSERT that files a
-- log, and the acknowledge UPDATE. There is NO edit-log path anywhere (`editLog` / `openEditLog` /
-- `updateLog` = 0 matches). So the content is already write-once in practice.
--
-- THE RULE. A filed progress report is a RECORD:
--   * its content (what was reported, by whom, for when) is immutable once filed
--   * acknowledging is a supervisor act
--   * and a supervisor may not acknowledge their OWN report — that is not review, it is signature
--
-- service_role / seeders keep their reach (auth.uid() IS NULL), as everywhere else in these arcs.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.guard_progress_log_is_a_record()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_is_sup   boolean;
  v_me       text;
BEGIN
  IF auth.uid() IS NULL THEN
    RETURN NEW;                              -- service_role / seeders / migrations
  END IF;

  -- 1. The REPORT itself is immutable. Only the acknowledgement fields may move.
  IF NEW.project_id    IS DISTINCT FROM OLD.project_id
     OR NEW.hive_id    IS DISTINCT FROM OLD.hive_id
     OR NEW.log_date   IS DISTINCT FROM OLD.log_date
     OR NEW.reported_by IS DISTINCT FROM OLD.reported_by
     OR NEW.pct_complete IS DISTINCT FROM OLD.pct_complete
     OR NEW.hours_worked IS DISTINCT FROM OLD.hours_worked
     OR NEW.notes      IS DISTINCT FROM OLD.notes
     OR NEW.blockers   IS DISTINCT FROM OLD.blockers
  THEN
    RAISE EXCEPTION 'A filed progress report cannot be edited (% on %). File a new report instead, '
                    'so the original stays on record.', OLD.reported_by, OLD.log_date
      USING ERRCODE = 'check_violation';
  END IF;

  -- 2. Acknowledging is a supervisor act.
  IF OLD.acknowledged_at IS NULL AND NEW.acknowledged_at IS NOT NULL THEN
    SELECT EXISTS (
      SELECT 1 FROM public.hive_members hm
       WHERE hm.hive_id = NEW.hive_id AND hm.auth_uid = auth.uid()
         AND hm.status = 'active' AND hm.role = 'supervisor'
    ) INTO v_is_sup;

    IF NOT v_is_sup THEN
      RAISE EXCEPTION 'Acknowledging a progress report is a supervisor action.'
        USING ERRCODE = 'insufficient_privilege';
    END IF;

    -- 3. ...and not of your OWN report. Reviewing your own work is a signature, not a review.
    --    Matched on the acting member's worker_name, because reported_by is a NAME on this table —
    --    there is no auth_uid here (six of seven project tables lack one), which is itself the
    --    open half of PJK1 and the reason this check cannot be stronger than a name comparison yet.
    SELECT hm.worker_name INTO v_me
      FROM public.hive_members hm
     WHERE hm.hive_id = NEW.hive_id AND hm.auth_uid = auth.uid() AND hm.status = 'active'
     LIMIT 1;

    IF v_me IS NOT NULL AND lower(trim(v_me)) = lower(trim(COALESCE(OLD.reported_by, ''))) THEN
      RAISE EXCEPTION 'You cannot acknowledge your own progress report (%). Another supervisor must '
                      'review it.', OLD.reported_by
        USING ERRCODE = 'insufficient_privilege';
    END IF;
  END IF;

  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_progress_log_is_a_record ON public.project_progress_logs;
CREATE TRIGGER trg_progress_log_is_a_record
  BEFORE UPDATE ON public.project_progress_logs
  FOR EACH ROW
  EXECUTE FUNCTION public.guard_progress_log_is_a_record();

COMMENT ON FUNCTION public.guard_progress_log_is_a_record() IS
  'A filed progress report is a RECORD: its content is immutable, acknowledging it is a supervisor '
  'act, and nobody may acknowledge their own report. Before this, a worker could rewrite another '
  'worker''s log to claim 100% while the row still named the original reporter, and could '
  'self-acknowledge. The self-check compares worker_name because project_progress_logs has no '
  'auth_uid — that gap is PJK1''s open half. PJ6.';
