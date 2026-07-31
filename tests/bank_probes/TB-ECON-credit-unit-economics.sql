-- TB-ECON-credit-unit-economics.sql
--
-- UNIT ECONOMICS (MARKETPLACE_CREDIT_ECONOMY.md §7.4). Ian proposed 5% at listing + 1% consumer cashback;
-- the refinement argues for 5% on completion instead. This cell deliberately asserts the arithmetic under
-- BOTH policies, because the money must add up whichever timing he picks — a test that only worked for the
-- recommendation would be advocacy, not verification.
--
-- THE THREE PROPERTIES THAT MAKE A CREDIT ECONOMY SURVIVABLE:
--   1. NET TAKE IS WHAT WE THINK IT IS. Cashback is funded from the take, so net = fees - cashback. If that
--      arithmetic is ever wrong the platform learns it from a shrinking balance months later, one job at a
--      time.
--   2. THE PLATFORM CANNOT PAY OUT MORE THAN IT TAKES IN. A policy where cashback exceeds the fees mints
--      credits nobody earned - a slow insolvency that looks like generosity on every single transaction.
--   3. CASHBACK CANNOT MINT WITHOUT A SETTLED JOB. Otherwise a self-dealt request prints credits, which is
--      the shape the marketplace trust guards refuse everywhere else.
--
-- Rates are read through the RESOLVER, never hardcoded here: a probe that restates the numbers would pass
-- while the product used different ones, which is how a denominator and a pipeline drift apart.
begin;

insert into auth.users(id, email) values ('60000000-0000-4000-8000-00000000000a','tb-econ@gate.local');

do $probe$
declare
  H constant uuid := '084c113b-99c0-45c6-a8e8-b4b8349da46d';
  PRICE constant numeric := 2000;
  v_comm numeric; v_list numeric; v_cash numeric; v_net numeric; v_minted numeric; n int;
begin
  insert into public.hive_service_settings(hive_id) values (H) on conflict (hive_id) do nothing;

  -- ── POLICY A: the roadmap model (commission on completion) ──────────────────────────────────────────
  update public.hive_service_settings
     set commission_pct = 5.00, listing_fee_pct = 0.00, cashback_pct = 1.00 where hive_id = H;
  v_comm := public.service_knob_pct(H,'commission_pct');
  v_list := public.service_knob_pct(H,'listing_fee_pct');
  v_cash := public.service_knob_pct(H,'cashback_pct');
  v_net  := v_comm + v_list - v_cash;
  raise notice 'RESULT policyA_net_take_pct=%', v_net;
  raise notice 'RESULT policyA_net_on_2000=%', round(PRICE * v_net / 100.0, 2);

  -- ── POLICY B: Ian's model (fee at listing), expressed purely as config ──────────────────────────────
  update public.hive_service_settings
     set commission_pct = 0.00, listing_fee_pct = 5.00, cashback_pct = 1.00 where hive_id = H;
  v_net := public.service_knob_pct(H,'commission_pct')
         + public.service_knob_pct(H,'listing_fee_pct')
         - public.service_knob_pct(H,'cashback_pct');
  raise notice 'RESULT policyB_net_take_pct=%', v_net;

  -- ── SOLVENCY: paying out more than we take in must be structurally impossible ───────────────────────
  begin
    update public.hive_service_settings set cashback_pct = 9.00 where hive_id = H;
    raise notice 'RESULT insolvent_policy=ACCEPTED';
  exception when others then raise notice 'RESULT insolvent_policy=blocked'; end;
  update public.hive_service_settings set cashback_pct = 1.00 where hive_id = H;

  -- ── CASHBACK ONLY ON A SETTLED JOB ──────────────────────────────────────────────────────────────────
  insert into public.service_requests(id, client_auth_uid, hive_id, status, mode, custom_scope, budget)
  values ('60000000-0000-4000-8000-0000000000d1','60000000-0000-4000-8000-00000000000a',H,
          'in_progress','instant','TB econ job', PRICE);
  v_minted := public.mint_service_cashback('60000000-0000-4000-8000-0000000000d1');
  raise notice 'RESULT cashback_before_settled=%', v_minted;

  update public.service_requests set status = 'settled'
   where id = '60000000-0000-4000-8000-0000000000d1';
  v_minted := public.mint_service_cashback('60000000-0000-4000-8000-0000000000d1');
  raise notice 'RESULT cashback_on_settled=%', v_minted;

  -- NON-VACUITY: the amount must MATCH the configured rate, not merely be non-zero. A hardcoded 1% would
  -- pass a "> 0" assertion while ignoring the knob entirely.
  raise notice 'RESULT cashback_matches_rate=%',
    case when v_minted = round(PRICE * public.service_knob_pct(H,'cashback_pct') / 100.0, 2)
         then 'yes' else 'NO' end;

  -- and it is a LEDGER liability, once
  select count(*) into n from public.service_credit_ledger
   where entry_type = 'cashback' and ref_id = '60000000-0000-4000-8000-0000000000d1'::uuid;
  raise notice 'RESULT cashback_ledger_rows=%', n;
end $probe$;

rollback;
