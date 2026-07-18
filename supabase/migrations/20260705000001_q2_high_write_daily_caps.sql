-- Q2 -- Free-Tier Quota Roadmap: replicate the Q0 per-day cap to the high-write tables.
-- =====================================================================================
-- FREE_TIER_QUOTA_ROADMAP Phase Q2. Q0 proved the "bounded page" pattern on logbook;
-- this generalises it to every other high-write table with ONE reusable, seeder-safe
-- generic trigger function + one BEFORE INSERT trigger per table.
--
-- WHY generic (not 6 copies of check_logbook_rate_limit): the only per-table differences
-- are (cap, timestamp column, identity column). A single function parameterised via
-- TG_ARGV keeps the logic in one audited place and is the substrate Q5's unified quota
-- board extends. Dynamic SQL uses %I identifier quoting (injection-safe; args are
-- developer constants), and reads the identity generically via to_jsonb(NEW)->>col.
--
-- PHANTOM-COLUMN GUARD (the lesson from Q0): each table's REAL timestamp column is passed
-- explicitly -- pm_completions has NO `created_at`, its timestamp is `completed_at`.
-- Hard-coding created_at everywhere would re-break pm_completions inserts.
--
-- SEEDER-SAFE: counts rows created TODAY (Asia/Manila) via a sargable range on each
-- table's timestamp column, so the 5-year synthetic seeder's historical backfill never
-- counts -- only a live same-day flood trips the cap.
--
-- Caps are cost-weighted, generous for a real 20-person hive, brutal for a script:
--   inventory_transactions 1000/day/hive (stock in/out is the highest-volume surface)
--   inventory_items         500/day/hive   pm_completions 500/day/hive (completed_at!)
--   community_posts         200/day/hive   community_replies 500/day/hive
--   asset_nodes             200/day/hive (the baseline `assets` table was DROPPED in
--                           20260512000009 and replaced by asset_nodes — target the REAL table)
-- Per-user/day sub-caps (the abuse stop) are ~40-60% of the hive cap. Q5 adds per-hive
-- tunability via a unified hive_daily_caps table; Q2 ships generous constant defaults.
--
-- NOTE: `checklist_records` from the roadmap's Q2 list DOES NOT EXIST in any migration
-- (zero references) -- it is a phantom table name. And the baseline `assets` table was
-- DROPPED (20260512000009) in favour of `asset_nodes` -- so we target asset_nodes, the
-- real table. Covered here: the 6 real high-write tables. (The live apply caught the
-- assets/asset_nodes swap that static CREATE-TABLE parsing missed.)

BEGIN;

CREATE OR REPLACE FUNCTION public.check_daily_row_cap()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  hive_cap    integer := (TG_ARGV[0])::int;   -- default per-hive/day cap
  ts_col      text    := TG_ARGV[1];          -- timestamp column for the day window (created_at / completed_at)
  ident_col   text    := TG_ARGV[2];          -- identity column (worker_name / author_name)
  user_cap    integer := (TG_ARGV[3])::int;   -- default per-user/day cap
  day_start   timestamptz := (date_trunc('day', now() AT TIME ZONE 'Asia/Manila')) AT TIME ZONE 'Asia/Manila';
  day_end     timestamptz := day_start + INTERVAL '1 day';
  -- Read hive_id GENERICALLY (via jsonb) so this fn works on solo tables that
  -- have NO hive_id column too — there NEW.hive_id would raise "record has no
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
      -- (No automation_log write: a RAISE aborts the statement and would roll the log
      --  row back anyway; 'warn' also isn't an allowed status. 54000 is the signal.)
      RAISE EXCEPTION 'You have reached today''s free limit (%). Resets at midnight.', hive_cap
        USING ERRCODE = '54000', HINT = 'daily_hive_' || TG_TABLE_NAME;
    END IF;
  END IF;

  -- Per-USER/day cap -- the abuse stop. Keyed on the table's identity column.
  IF ident_val IS NOT NULL AND ident_col <> '' THEN
    EXECUTE format(
      'SELECT count(*) FROM public.%I WHERE %I >= $1 AND %I < $2 AND %I = $3',
      TG_TABLE_NAME, ts_col, ts_col, ident_col)
      INTO user_n USING day_start, day_end, ident_val;
    IF user_n >= user_cap THEN
      RAISE EXCEPTION 'You have reached today''s free limit (%). Resets at midnight.', user_cap
        USING ERRCODE = '54000', HINT = 'daily_user_' || TG_TABLE_NAME;
    END IF;
  END IF;

  RETURN NEW;
END;
$$;

ALTER FUNCTION public.check_daily_row_cap() OWNER TO postgres;

-- One BEFORE INSERT trigger per real high-write table. TG_ARGV = (hive_cap, ts_col, ident_col, user_cap).
DROP TRIGGER IF EXISTS trg_daily_cap_inv_tx ON public.inventory_transactions;
CREATE TRIGGER trg_daily_cap_inv_tx BEFORE INSERT ON public.inventory_transactions
  FOR EACH ROW EXECUTE FUNCTION public.check_daily_row_cap('1000', 'created_at', 'worker_name', '400');

DROP TRIGGER IF EXISTS trg_daily_cap_inv_items ON public.inventory_items;
CREATE TRIGGER trg_daily_cap_inv_items BEFORE INSERT ON public.inventory_items
  FOR EACH ROW EXECUTE FUNCTION public.check_daily_row_cap('500', 'created_at', 'worker_name', '200');

DROP TRIGGER IF EXISTS trg_daily_cap_pm_comp ON public.pm_completions;
CREATE TRIGGER trg_daily_cap_pm_comp BEFORE INSERT ON public.pm_completions
  FOR EACH ROW EXECUTE FUNCTION public.check_daily_row_cap('500', 'completed_at', 'worker_name', '200');

DROP TRIGGER IF EXISTS trg_daily_cap_comm_posts ON public.community_posts;
CREATE TRIGGER trg_daily_cap_comm_posts BEFORE INSERT ON public.community_posts
  FOR EACH ROW EXECUTE FUNCTION public.check_daily_row_cap('200', 'created_at', 'author_name', '100');

DROP TRIGGER IF EXISTS trg_daily_cap_comm_replies ON public.community_replies;
CREATE TRIGGER trg_daily_cap_comm_replies BEFORE INSERT ON public.community_replies
  FOR EACH ROW EXECUTE FUNCTION public.check_daily_row_cap('500', 'created_at', 'author_name', '200');

DROP TRIGGER IF EXISTS trg_daily_cap_asset_nodes ON public.asset_nodes;
CREATE TRIGGER trg_daily_cap_asset_nodes BEFORE INSERT ON public.asset_nodes
  FOR EACH ROW EXECUTE FUNCTION public.check_daily_row_cap('200', 'created_at', 'worker_name', '100');

COMMIT;
