-- 20261026000009_a_double_fire_leaves_one_effect.sql
--
-- THREE SCHEDULED JOBS DID THEIR WORK AGAIN WHEN FIRED TWICE (OWN scheduled-work lens, 2026-10-26). A job fires twice
-- when someone re-runs it by hand, when a deploy re-schedules it mid-window, or when two schedulers overlap; the effect
-- must be the same as one fire. Read from the functions' own bodies:
--
--   listing-holding-fee-monthly  sweep_listing_holding_fee() charged every held reservation of a live listing on every
--                                call. Nothing remembered that this month was already charged: a second fire charged
--                                every seller the monthly fee again and retired the credits again.
--   ops-db-size-snapshot-daily   snapshot_db_size() inserted a point on every call: two points for one day.
--   ai-eval-daily-*              the nightly slices share one run_id per UTC night, and ai-eval-runner inserted a row
--                                per fixture per call: a second fire doubled the night's rows (and its model spend).
--
-- Now: the holding fee is charged once per listing per UTC month - the sweep skips a listing this month already paid
-- and the ledger refuses a second holding_fee for one listing in one month; the snapshot keeps one row per UTC day (a
-- second fire refreshes it); ai_quality_log holds one row per run, agent and question (the runner skips a fixture the
-- run already graded and replaces one that ended in an infrastructure error). Concurrent fires are serialised with a
-- transaction advisory lock, so two at once cannot both pass the check.

-- ── the holding fee: once per listing per month ──────────────────────────────────────────────────────────────────────
CREATE UNIQUE INDEX IF NOT EXISTS service_credit_ledger_one_holding_fee_per_listing_month
  ON public.service_credit_ledger (ref_id, (date_trunc('month', created_at AT TIME ZONE 'UTC')))
  WHERE entry_type = 'holding_fee';

CREATE OR REPLACE FUNCTION public.sweep_listing_holding_fee()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
declare v_rate numeric; v_charged numeric := 0; v_n int := 0; v_skipped int := 0; r record;
begin
  -- one sweep at a time: a second, concurrent fire waits here and then finds this month already charged
  perform pg_advisory_xact_lock(hashtext('sweep_listing_holding_fee'));
  for r in
    select cr.id, cr.amount, cr.seller_name, cr.hive_id, cr.listing_id, ms.auth_uid
      from public.credit_reservations cr
      join public.marketplace_listings l on l.id = cr.listing_id
      left join public.marketplace_sellers ms on ms.worker_name = cr.seller_name
     where cr.state = 'held' and l.status = 'published'
  loop
    if exists (select 1 from public.service_credit_ledger x
                where x.entry_type = 'holding_fee' and x.ref_id = r.listing_id
                  and date_trunc('month', x.created_at AT TIME ZONE 'UTC') = date_trunc('month', now() AT TIME ZONE 'UTC')) then
      v_skipped := v_skipped + 1;
      continue;
    end if;
    v_rate := public.service_knob_pct(r.hive_id, 'holding_fee_pct') / 100.0;
    continue when v_rate <= 0 or r.auth_uid is null;
    declare v_fee numeric := round(r.amount * v_rate, 2);
    begin
      continue when v_fee <= 0;
      update public.credit_reservations set amount = greatest(0, amount - v_fee) where id = r.id;
      insert into public.service_credit_ledger
        (account_type, account_id, entry_type, amount, ref_kind, ref_id, note)
      values ('consumer', r.auth_uid, 'holding_fee', -v_fee, 'listing', r.listing_id,
              'monthly holding fee on a live listing');
      perform public.retire_credits(v_fee);
      v_charged := v_charged + v_fee; v_n := v_n + 1;
    end;
  end loop;
  return jsonb_build_object('listings_charged', v_n, 'credits_retired', v_charged, 'already_charged_this_month', v_skipped);
end
$$;

-- ── the database-size snapshot: one row per UTC day ───────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.snapshot_db_size()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_catalog
AS $$
DECLARE
  v_db      bigint  := pg_database_size(current_database());
  v_storage bigint  := COALESCE((SELECT sum(bytes) FROM public.v_storage_health), 0);
  v_tables  integer := (SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public');
BEGIN
  PERFORM pg_advisory_xact_lock(hashtext('snapshot_db_size'));
  UPDATE public.ops_db_size_history
     SET captured_at = now(), db_bytes = v_db, storage_bytes = v_storage, table_count = v_tables
   WHERE (captured_at AT TIME ZONE 'UTC')::date = (now() AT TIME ZONE 'UTC')::date;
  IF NOT FOUND THEN
    INSERT INTO public.ops_db_size_history (captured_at, db_bytes, storage_bytes, table_count)
    VALUES (now(), v_db, v_storage, v_tables);
  END IF;
END
$$;

-- ── the nightly AI eval: one row per run, agent and question ──────────────────────────────────────────────────────────
-- a duplicate that predates this keeps its newest row (none existed on 2026-10-26, locally or in production)
DELETE FROM public.ai_quality_log a
 USING public.ai_quality_log b
 WHERE a.run_id IS NOT NULL AND a.run_id = b.run_id AND a.agent_id = b.agent_id AND a.question_id = b.question_id
   AND a.ctid < b.ctid;
CREATE UNIQUE INDEX IF NOT EXISTS ai_quality_log_one_row_per_run_question
  ON public.ai_quality_log (run_id, agent_id, question_id);
