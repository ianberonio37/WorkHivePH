-- ─────────────────────────────────────────────────────────────────────────────
-- The PJ17 attribution pin does the platform's job under a name the platform does not recognise.
--
-- 20260728000033 added `auth_uid` to project_progress_logs and a BEFORE INSERT trigger that stamps
-- it and forces `reported_by` to the caller's own worker_name. Correct behaviour — and it made the
-- DB-adoption census FAIL, which was the census being right rather than noisy:
--
--     D2 (hive-membership scoping policy) adoption fell 98 -> 97 — dropped by: project_progress_logs
--     Verdict: FLAGS: has auth_uid + a CLIENT-WRITABLE policy that does NOT self-pin auth_uid
--              AND no bind_* trigger — ATTRIBUTION-FORGERY suspect.
--
-- Adding the column is what put the table under that rule. The rule's two escapes are a policy that
-- pins `auth_uid = auth.uid()`, or a `bind_*` trigger — which the census explicitly prefers:
-- "a bind_* trigger is the STRONGER pin (server-side, immune to policy drift)". The table has
-- exactly that pin. It is called `guard_progress_log_is_mine`, so the detector could not see it.
--
-- WHY RENAME RATHER THAN TEACH THE DETECTOR. Normally the answer is to teach the gate — a name is
-- not evidence, and a naming-convention check is weaker than reading what a trigger does. But here
-- the convention is already carried by dozens of tables (bind_acknowledged_by_from_hive,
-- bind_asset_nodes_submitter, bind_community_post_submitter, ...) and it is load-bearing in the
-- census. Adding a SECOND accepted spelling would leave the platform with two names for one
-- mechanism and a detector that has to know both. Joining the convention keeps one way of saying
-- "this column is pinned server-side", and it is the convention that is right.
--
-- Behaviour is unchanged: same body, same guarantees, same verification. Only the names move.
-- ─────────────────────────────────────────────────────────────────────────────

DROP TRIGGER IF EXISTS trg_progress_log_is_mine ON public.project_progress_logs;
DROP FUNCTION IF EXISTS public.guard_progress_log_is_mine();

CREATE OR REPLACE FUNCTION public.bind_progress_log_submitter()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_me text;
BEGIN
  IF auth.uid() IS NULL THEN
    RETURN NEW;                                   -- service_role / seeders / migrations
  END IF;

  SELECT hm.worker_name INTO v_me
    FROM public.hive_members hm
   WHERE hm.hive_id = NEW.hive_id
     AND hm.auth_uid = auth.uid()
     AND hm.status = 'active'
   LIMIT 1;

  IF v_me IS NULL THEN
    RAISE EXCEPTION 'You are not an active member of this hive, so you cannot file a progress '
                    'report in it.'
      USING ERRCODE = 'insufficient_privilege';
  END IF;

  NEW.auth_uid    := auth.uid();
  NEW.reported_by := v_me;                        -- the name is the caller's, not the caller's choice

  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_bind_progress_log_submitter ON public.project_progress_logs;
CREATE TRIGGER trg_bind_progress_log_submitter
  BEFORE INSERT ON public.project_progress_logs
  FOR EACH ROW
  EXECUTE FUNCTION public.bind_progress_log_submitter();

COMMENT ON FUNCTION public.bind_progress_log_submitter() IS
  'BEFORE INSERT on project_progress_logs: stamps auth_uid and forces reported_by to the caller''s '
  'own hive_members.worker_name. Proven live before the fix — a supervisor filed a report as '
  '"Bryan Garcia" and it was accepted, which also defeated migration 027''s no-self-ack rule (that '
  'rule is matched on reported_by, so filing under a colleague''s name let you acknowledge your own '
  'work). Named to the platform''s bind_* convention so the DB-adoption census recognises the pin. '
  'PJ17/PJ16, 2026-07-28.';
