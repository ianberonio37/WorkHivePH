-- 20260731000022_restore_daily_cap_uuid_cast.sql
--
-- CARRIES FORWARD THE `%I::text = $3` CAST, WHICH IS LOAD-BEARING.
--
-- What happened: rebuilding `check_daily_row_cap` from a PARTIAL read of prosrc silently dropped the cast.
-- `ident_val` comes from `to_jsonb(NEW) ->> ident_col` and is always TEXT, while ident_col may be a UUID
-- column (service_requests.client_auth_uid, resume_versions.auth_uid). Without the cast Postgres raises
-- 42883 `operator does not exist: uuid = text` and EVERY insert into such a table fails. Migration
-- 20260709000000_fix_daily_cap_uuid_ident.sql had fixed exactly this a month earlier.
--
-- WHY A NEW FILE. The fix was first applied by EDITING 20260731000005 in place, and the
-- migration-immutability gate caught that and was right: Supabase tracks applied migrations BY FILENAME, so
-- a database that already ran ...005 would never see the correction — production would keep the FIRST,
-- broken version forever while the repo looked correct. ...005 is restored to its first committed content
-- and the fix lives here, where a fresh timestamp guarantees it runs.
--
-- THE BODY BELOW IS THE LIVE DEFINITION, DUMPED FROM pg_get_functiondef — NOT RETYPED. Writing it from
-- memory a second time produced a function that dropped HIVE SCOPING (hive_cap/hive_id_val) and the
-- Asia/Manila day boundary, on a platform whose users are all in Manila. That draft was caught only by
-- byte-diffing the rebuild against the live function before trusting it. Read the whole thing, or dump it.
CREATE OR REPLACE FUNCTION public.check_daily_row_cap()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  hive_cap    integer := (TG_ARGV[0])::int;
  ts_col      text    := TG_ARGV[1];
  ident_col   text    := TG_ARGV[2];
  user_cap    integer := (TG_ARGV[3])::int;
  day_start   timestamptz := (date_trunc('day', now() AT TIME ZONE 'Asia/Manila')) AT TIME ZONE 'Asia/Manila';
  day_end     timestamptz := day_start + INTERVAL '1 day';
  hive_id_val uuid    := NULLIF(to_jsonb(NEW) ->> 'hive_id', '')::uuid;
  ident_val   text    := to_jsonb(NEW) ->> ident_col;
  hive_n      integer;
  user_n      integer;
BEGIN
  -- ANNOUNCED SYSTEM WRITE: a bulk operator opts in explicitly for the statement/transaction. Everything
  -- below is byte-identical to the version this replaces — only this branch is new, deliberately, so the
  -- change cannot alter the cap's behaviour for any ordinary caller.
  IF current_setting('workhive.row_cap_system_write', true) = 'on' THEN
    RETURN NEW;
  END IF;

  IF hive_id_val IS NOT NULL THEN
    EXECUTE format(
      'SELECT count(*) FROM public.%I WHERE hive_id = $1 AND %I >= $2 AND %I < $3',
      TG_TABLE_NAME, ts_col, ts_col)
      INTO hive_n USING hive_id_val, day_start, day_end;
    IF hive_n >= hive_cap THEN
      RAISE EXCEPTION 'You have reached today''s free limit (%). Resets at midnight.', hive_cap
        USING ERRCODE = '54000', HINT = 'daily_hive_' || TG_TABLE_NAME;
    END IF;
  END IF;

  -- `%I::text = $3` — the cast is LOAD-BEARING and was restored after I regressed it. `ident_val` comes from
  -- `to_jsonb(NEW) ->> ident_col`, which is always TEXT, while ident_col may be a UUID column
  -- (service_requests.client_auth_uid, resume_versions.auth_uid). Without the cast Postgres raises
  -- 42883 `operator does not exist: uuid = text` and EVERY insert into such a table fails.
  --
  -- Migration 20260709000000_fix_daily_cap_uuid_ident.sql fixed exactly this a month ago. I rebuilt this
  -- function from a PARTIAL read of prosrc (three truncated substring() queries) and silently dropped the
  -- cast, re-opening a closed bug — the precise failure of
  -- [[feedback_i_rebuilt_a_guard_from_a_partial_read]]. Read the WHOLE function, or better, read the
  -- migration that last defined it.
  IF ident_val IS NOT NULL AND ident_col <> '' THEN
    EXECUTE format(
      'SELECT count(*) FROM public.%I WHERE %I >= $1 AND %I < $2 AND %I::text = $3',
      TG_TABLE_NAME, ts_col, ts_col, ident_col)
      INTO user_n USING day_start, day_end, ident_val;
    IF user_n >= user_cap THEN
      RAISE EXCEPTION 'You have reached today''s free limit (%). Resets at midnight.', user_cap
        USING ERRCODE = '54000', HINT = 'daily_user_' || TG_TABLE_NAME;
    END IF;
  END IF;

  RETURN NEW;
END
$function$

