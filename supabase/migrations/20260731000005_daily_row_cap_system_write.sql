-- 20260731000005_daily_row_cap_system_write.sql
--
-- `check_daily_row_cap` is a per-user/per-hive ABUSE cap (200/day on fault_knowledge, etc). It is the ONLY
-- guard of its class on this platform with NO sanctioned operator path: every sibling guard allows a vetted
-- backend write via `auth.uid() IS NULL` and/or an ANNOUNCED `workhive.*_system_write` GUC. This one applies
-- to everyone, so a legitimate bulk operation — a backfill, a restore, a seeder, a migration — hits an
-- anti-spam limit meant for a human clicking a button.
--
-- Found 2026-07-31 driving the auto-embed backfill: 2,200 queued rows stopped at
-- `ERROR: You have reached today's free limit (200) / HINT: daily_user_fault_knowledge`. The cap was doing
-- exactly its job; the gap is that no operation can ever legitimately exceed it.
--
-- THE FIX IS THE PLATFORM'S OWN CONVENTION, not a hole. An ANNOUNCED system write must opt IN, per statement
-- or per transaction, by setting `workhive.row_cap_system_write = 'on'`. That is deliberately noisy: it
-- appears in the caller's code, so a reader can see the cap was bypassed on purpose. A raw client cannot set
-- it (a GUC set inside a transaction by the writer is the announcement), and the cap stays fully in force for
-- every ordinary write.
--
-- Deliberately NOT an `auth.uid() IS NULL` bypass. That would exempt EVERY service-role write — including the
-- edge functions users trigger indirectly — which is far broader than "an operator is running a bulk job",
-- and would quietly retire an abuse cap the platform relies on.

CREATE OR REPLACE FUNCTION public.check_daily_row_cap()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $fn$
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
$fn$;
