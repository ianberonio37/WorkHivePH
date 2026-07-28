-- ─────────────────────────────────────────────────────────────────────────────
-- A progress report could be filed in someone else's name.
--
-- FOUND BY THE PJ17 WALK (2026-07-28), probed live from the page while signed in as Leandro
-- Marquez (supervisor, Baguio Textile Mills):
--
--     INSERT INTO project_progress_logs (..., reported_by, pct_complete)
--     VALUES (..., 'Bryan Garcia', 99)          ->  ACCEPTED, filed as Bryan Garcia
--
-- `project_progress_logs` has NO auth_uid column at all. The only attribution is `reported_by`, a
-- free-text name the client chooses. RLS scopes the row to the hive and stops there, so any active
-- member can file a report under any colleague's name.
--
-- WHY IT MATTERS MORE THAN A MISLABELLED ROW:
--   * a supervisor ACKNOWLEDGES these reports — 20260728000027 made acknowledgement a supervisor
--     act with no self-ack, which turns an acknowledged report into a signed-off record. Signing
--     off on a report means signing off on WHO filed it.
--   * they feed v_project_progress_truth, and through it the Earned Value hours and the project
--     rollup. A report is not just a note; it moves the numbers a client is shown.
--   * the no-self-ack rule in 027 is MATCHED ON reported_by. So filing under someone else's name
--     also defeats that check: write the report as a colleague, then acknowledge it yourself.
--
-- 20260728000027 saw half of this. Its header already observed that the row "still reads
-- reported_by = Leandro Marquez", but it is a BEFORE UPDATE trigger — it froze the content and
-- gated the acknowledgement, and never touched the INSERT that decides whose name goes on it.
--
-- THE FIX, AND WHY IT FORCES RATHER THAN REFUSES. The trigger stamps auth_uid from auth.uid() and
-- OVERWRITES reported_by with the caller's own worker_name. It does not raise on a mismatch:
--   * the value is an identity CLAIM, not user content — forcing it is the same discipline as a
--     DEFAULT auth.uid() column, and it makes forgery impossible rather than merely detected;
--   * the page already sends its own WORKER_NAME, so in every legitimate flow this is a no-op;
--   * raising would turn any drift between a display name and a membership name into a hard write
--     failure for an honest field worker, which is a bad trade for a check the force already wins.
-- A caller who is not an active member of the hive IS refused — they have no name to write.
--
-- The column is nullable: seeded and service_role rows (auth.uid() IS NULL) legitimately have no
-- auth identity behind them, exactly as elsewhere in these arcs.
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE public.project_progress_logs
  ADD COLUMN IF NOT EXISTS auth_uid uuid;

COMMENT ON COLUMN public.project_progress_logs.auth_uid IS
  'Auth identity that filed this report. NULL only for seeded/service_role rows. Added PJ17 after a '
  'live probe filed a report under another worker''s name — reported_by alone is client-chosen text.';

CREATE INDEX IF NOT EXISTS idx_progress_logs_auth_uid
  ON public.project_progress_logs (auth_uid)
  WHERE auth_uid IS NOT NULL;

CREATE OR REPLACE FUNCTION public.guard_progress_log_is_mine()
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

DROP TRIGGER IF EXISTS trg_progress_log_is_mine ON public.project_progress_logs;
CREATE TRIGGER trg_progress_log_is_mine
  BEFORE INSERT ON public.project_progress_logs
  FOR EACH ROW
  EXECUTE FUNCTION public.guard_progress_log_is_mine();

COMMENT ON FUNCTION public.guard_progress_log_is_mine() IS
  'BEFORE INSERT on project_progress_logs: stamps auth_uid and forces reported_by to the caller''s '
  'own hive_members.worker_name. Proven live before the fix — a supervisor filed a report as '
  '"Bryan Garcia" and it was accepted, which also defeated 027''s no-self-ack rule (that rule is '
  'matched on reported_by, so filing under a colleague''s name lets you acknowledge your own work). '
  'PJ17/PJK1, 2026-07-28.';
