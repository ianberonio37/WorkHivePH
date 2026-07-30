-- =====================================================================
-- SERVICE HAILING · per-day write caps on the client-writable service tables
-- =====================================================================
-- The quota-page-audit gate caught 4 uncapped feature-page write tables introduced by the
-- service-hailing arc. Three are genuine abuse vectors on a hailing platform:
--   * service_requests      - hail spam floods every provider's broadcast feed (the core one)
--   * service_credit_topups - filing spam floods the founder's GCash verification queue
--   * service_providers     - registration spam pollutes the provider directory
-- (push_subscriptions is the 4th; it is an UPSERT keyed on the device endpoint - one row per
--  device, re-registered rather than accumulated - so it carries a documented exclusion in
--  tools/quota_page_audit.py instead of a row cap.)
--
-- Caps reuse the platform's existing check_daily_row_cap() rather than inventing a parallel
-- mechanism. TG_ARGV = (hive_cap, ts_col, ident_col, user_cap); Asia/Manila day window.
--
-- ONE fix to the shared function first: its per-user cap compares the identity column to a
-- TEXT parameter, so a uuid identity column (client_auth_uid / payer_auth_uid / auth_uid)
-- raised `operator does not exist: uuid = text`. Casting the column to ::text in the dynamic
-- SQL is behaviour-identical for the 6 existing text-keyed tables (text::text = text) and
-- lets auth-uid-keyed tables be capped at all. Consumer hails have NO hive_id, so the
-- per-USER cap is the only stop that applies to them - it had to work on a uuid column.

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
  ident_col   text    := TG_ARGV[2];          -- identity column (worker_name / author_name / *_auth_uid)
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
  -- %I::text so a uuid identity column compares cleanly against the text $3 (see header).
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
$$;

ALTER FUNCTION public.check_daily_row_cap() OWNER TO postgres;

-- ── The three caps ───────────────────────────────────────────────────────────
-- service_requests: a plant filing 200 hails/day is already far beyond real use; one client
-- account filing 50 is the abuse stop (and the ONLY stop for hive-less consumers).
DROP TRIGGER IF EXISTS trg_daily_cap_service_requests ON public.service_requests;
CREATE TRIGGER trg_daily_cap_service_requests BEFORE INSERT ON public.service_requests
  FOR EACH ROW EXECUTE FUNCTION public.check_daily_row_cap('200', 'created_at', 'client_auth_uid', '50');

-- service_credit_topups: no hive_id column, so the hive arg is inert; 10/day per payer. A real
-- provider tops up once every few days - 10 filings in one day is queue flooding.
DROP TRIGGER IF EXISTS trg_daily_cap_service_topups ON public.service_credit_topups;
CREATE TRIGGER trg_daily_cap_service_topups BEFORE INSERT ON public.service_credit_topups
  FOR EACH ROW EXECUTE FUNCTION public.check_daily_row_cap('100', 'created_at', 'payer_auth_uid', '10');

-- service_providers: hive companies register once; freelancers once. 5/day per auth_uid is
-- generous (a supervisor registering several hive companies) and still stops directory spam.
DROP TRIGGER IF EXISTS trg_daily_cap_service_providers ON public.service_providers;
CREATE TRIGGER trg_daily_cap_service_providers BEFORE INSERT ON public.service_providers
  FOR EACH ROW EXECUTE FUNCTION public.check_daily_row_cap('50', 'created_at', 'auth_uid', '5');

COMMIT;
