-- Q0 -- Free-Tier Quota Roadmap: LOGBOOK PILOT (the reference implementation)
-- =========================================================================
-- FREE_TIER_QUOTA_ROADMAP.md Phase Q0. This is the TEMPLATE that every other
-- high-write table (Q2) will replicate. For the logbook page it delivers:
--   1. A per-day insert RATE LIMIT -- always-on hard block, the security-skill
--      documented pattern (check_logbook_rate_limit). Default 200/day/hive +
--      100/day/user, both tunable via hive_quotas.max_rows_logbook /
--      max_rows_logbook_per_user (NULL = default). The per-USER sub-cap is the
--      real abuse stop (roadmap decision F1).
--   2. Server-side TEXT-FIELD CAPS on problem/root_cause/action/knowledge --
--      defense-in-depth behind the client `maxlength`, which is bypassable.
--
-- WHY a fresh trigger, not the old check_hive_quota_logbook: that one
-- (20260511000003) counted CUMULATIVE rows and read max_rows_logbook; then
-- 20260520000004 dropped the column and 20260521126000 dropped the trigger
-- because the orphaned column reference broke EVERY logbook INSERT. This is a
-- distinct PER-DAY rate limit and it re-adds the tunable column CORRECTLY
-- (COALESCE default, so a missing column value can never break an insert).
--
-- SEEDER-SAFE: the count is over rows created TODAY (Asia/Manila) only, via a
-- sargable created_at range (uses idx_logbook_hive_date). The 5-year synthetic
-- seeder (tools/seed_5y_synthetic_history.py) writes historical created_at, so
-- its backfill never counts toward "today" -- only a live same-day flood trips
-- the cap. This preserves exactly what 20260521126000 unblocked.
--
-- Uses the REAL column `created_at` (the logbook table has no `logged_at`; the
-- skill's generic example used logged_at -- transcribing it verbatim would
-- reintroduce a "column does not exist" break).

BEGIN;

-- 1. Re-add the tunable per-day caps to hive_quotas (NULL = use code default).
ALTER TABLE public.hive_quotas ADD COLUMN IF NOT EXISTS max_rows_logbook          integer;
ALTER TABLE public.hive_quotas ADD COLUMN IF NOT EXISTS max_rows_logbook_per_user integer;

COMMENT ON COLUMN public.hive_quotas.max_rows_logbook IS
  'Q0: max logbook rows a hive may create per calendar day (Asia/Manila). NULL = default 200.';
COMMENT ON COLUMN public.hive_quotas.max_rows_logbook_per_user IS
  'Q0: max logbook rows one user may create per calendar day (Asia/Manila). NULL = default 100.';

-- 2. Per-day insert rate limit -- security-skill pattern, always-on hard block.
--    SECURITY DEFINER + locked search_path so it is unbypassable from the anon
--    key (per security skill: policy must key on the row's own hive/identity).
CREATE OR REPLACE FUNCTION public.check_logbook_rate_limit()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  hive_cap   integer;
  user_cap   integer;
  hive_n     integer;
  user_n     integer;
  -- Manila calendar-day window [day_start, day_start + 1 day) as a sargable
  -- created_at range (matches the "Resets at midnight" UX message).
  day_start  timestamptz := (date_trunc('day', now() AT TIME ZONE 'Asia/Manila')) AT TIME ZONE 'Asia/Manila';
  day_end    timestamptz := (date_trunc('day', now() AT TIME ZONE 'Asia/Manila') + INTERVAL '1 day') AT TIME ZONE 'Asia/Manila';
BEGIN
  -- Per-HIVE/day cap. Solo (no-hive) entries skip this but still get the user cap.
  IF NEW.hive_id IS NOT NULL THEN
    SELECT max_rows_logbook INTO hive_cap
      FROM public.hive_quotas WHERE hive_id = NEW.hive_id;
    hive_cap := COALESCE(hive_cap, 200);  -- no row OR NULL cap => default 200

    SELECT COUNT(*) INTO hive_n
      FROM public.logbook
      WHERE hive_id = NEW.hive_id
        AND created_at >= day_start AND created_at < day_end;

    IF hive_n >= hive_cap THEN
      -- No automation_log write here: this RAISE aborts the statement, which would
      -- roll the log row back anyway (and 'warn' isn't an allowed status). The 54000
      -- + friendly message IS the signal; durable over-quota telemetry is a separate
      -- non-blocking path (Q5).
      RAISE EXCEPTION 'You have logged today''s free limit (%). Resets at midnight.', hive_cap
        USING ERRCODE = '54000', HINT = 'logbook_daily_hive';
    END IF;
  END IF;

  -- Per-USER/day cap -- the real abuse stop (F1). Key on auth_uid, else worker_name.
  SELECT max_rows_logbook_per_user INTO user_cap
    FROM public.hive_quotas WHERE hive_id = NEW.hive_id;
  user_cap := COALESCE(user_cap, 100);

  SELECT COUNT(*) INTO user_n
    FROM public.logbook
    WHERE created_at >= day_start AND created_at < day_end
      AND (
        (NEW.auth_uid IS NOT NULL AND auth_uid = NEW.auth_uid)
        OR (NEW.auth_uid IS NULL AND worker_name = NEW.worker_name)
      );

  IF user_n >= user_cap THEN
    RAISE EXCEPTION 'You have logged today''s free limit (%). Resets at midnight.', user_cap
      USING ERRCODE = '54000', HINT = 'logbook_daily_user';
  END IF;

  RETURN NEW;
END;
$$;

ALTER FUNCTION public.check_logbook_rate_limit() OWNER TO postgres;

DROP TRIGGER IF EXISTS trg_logbook_rate_limit ON public.logbook;
CREATE TRIGGER trg_logbook_rate_limit
  BEFORE INSERT ON public.logbook
  FOR EACH ROW EXECUTE FUNCTION public.check_logbook_rate_limit();

-- 3. Server-side text-field caps (defense-in-depth; client maxlength is bypassable).
--    Caps MIRROR the client maxlength in logbook.html. Truncate rather than
--    reject so an over-long paste never loses the whole entry (the useful head
--    is kept). root_cause is a controlled <select>, so a short cap is ample.
CREATE OR REPLACE FUNCTION public.cap_logbook_text_fields()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.problem    IS NOT NULL THEN NEW.problem    := left(NEW.problem,    2000); END IF;
  IF NEW.root_cause IS NOT NULL THEN NEW.root_cause := left(NEW.root_cause,  200); END IF;
  IF NEW.action     IS NOT NULL THEN NEW.action     := left(NEW.action,     2000); END IF;
  IF NEW.knowledge  IS NOT NULL THEN NEW.knowledge  := left(NEW.knowledge,  2000); END IF;
  RETURN NEW;
END;
$$;

ALTER FUNCTION public.cap_logbook_text_fields() OWNER TO postgres;

DROP TRIGGER IF EXISTS trg_logbook_text_caps ON public.logbook;
CREATE TRIGGER trg_logbook_text_caps
  BEFORE INSERT OR UPDATE ON public.logbook
  FOR EACH ROW EXECUTE FUNCTION public.cap_logbook_text_fields();

COMMIT;
