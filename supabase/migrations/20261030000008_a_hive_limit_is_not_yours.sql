-- HS W2 (2026-10-30, the hive at thirty - found reading the caps a shift of thirty writes under): the shared daily cap
-- (check_daily_row_cap, on 29 tables) has two limits - the hive's, shared by every member, and the person's own. Both
-- refused in the same words, "You have reached today's free limit (100). Resets at midnight." In a hive of thirty the
-- hive's limit is spent by the other 29: the member it refuses has written nothing today, reads "You have reached",
-- and is told they did something they did not. The hive's branch now says whose limit it was and that nothing more is
-- saved until it resets - in words that hold for one write and for an import's rows alike (integrations.html shows it
-- under "79 assets were not imported:"); the person's own branch keeps its sentence. Everything else is the function exactly as it stands (read whole
-- from pg_get_functiondef - the uuid cast and the announced system write are kept). The same fix the logbook's own
-- hive cap took in 20261030000006.
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
      RAISE EXCEPTION 'Your hive has reached today''s free limit of % of these. No more can be saved until it resets at midnight.', hive_cap
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
$function$;
