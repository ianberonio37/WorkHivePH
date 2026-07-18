-- Fix: check_daily_row_cap() threw 42883 "operator does not exist: uuid = text"
-- on EVERY resume_versions insert, so resume version-history snapshots were 100%
-- dead (silently swallowed by snapshotVersion's best-effort catch). Root cause:
-- the shared daily-cap trigger reads the identity value as TEXT
--   ident_val text := to_jsonb(NEW) ->> ident_col;
-- then compares `%I = $3`. For the 25 tables whose ident_col is a TEXT column
-- (worker_name / author_name / email) that is text=text and works; but
-- resume_versions is capped on `auth_uid`, which is a UUID column -> uuid = text.
--
-- Fix: cast the identity column to ::text in the comparison. This is a no-op for
-- text ident columns (text::text = text) and correct for a uuid ident column
-- (uuid::text = text), so it works for all current + future callers regardless of
-- the identity column's type. Only the per-USER cap query changes; the per-HIVE
-- query already compares hive_id (uuid) against a uuid value.
-- Surfaced by the Resume-Builder page-deep PDDA arc live deepwalk (resume_versions
-- POST returned 404 mapping a 42883). See RESUME_BUILDER_DEEP_ARC.md.

CREATE OR REPLACE FUNCTION public.check_daily_row_cap()
  RETURNS trigger
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  hive_cap    integer := (TG_ARGV[0])::int;   -- default per-hive/day cap
  ts_col      text    := TG_ARGV[1];          -- timestamp column for the day window (created_at / completed_at)
  ident_col   text    := TG_ARGV[2];          -- identity column (worker_name / author_name / auth_uid)
  user_cap    integer := (TG_ARGV[3])::int;   -- default per-user/day cap
  day_start   timestamptz := (date_trunc('day', now() AT TIME ZONE 'Asia/Manila')) AT TIME ZONE 'Asia/Manila';
  day_end     timestamptz := day_start + INTERVAL '1 day';
  -- Read hive_id GENERICALLY (via jsonb) so this fn works on solo tables that
  -- have NO hive_id column too -- there NEW.hive_id would raise "record has no
  -- field hive_id". Absent/blank => NULL => hive cap skipped, identity cap applies.
  hive_id_val uuid    := NULLIF(to_jsonb(NEW) ->> 'hive_id', '')::uuid;
  ident_val   text    := to_jsonb(NEW) ->> ident_col;
  hive_n      integer;
  user_n      integer;
BEGIN
  -- Per-HIVE/day cap.
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

  -- Per-USER/day cap -- the abuse stop. Keyed on the table's identity column.
  -- Cast the column to ::text so a UUID identity column (resume_versions.auth_uid)
  -- compares correctly against the text-extracted ident_val (was uuid = text -> 42883).
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
END;
$function$;
