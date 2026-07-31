-- TB-A3-d9-knobs-configurable.sql
--
-- Closes A3 (configurability) on TB-A345 — the last owed obligation on the board. Ian chose ALL THREE knob
-- groups; migration 20260731000007 created them and 20260731000008 pointed the sweep at the resolver.
--
-- WHAT MAKES THIS A REAL CLOSURE RATHER THAN A DECLARED ONE: a knob nobody reads is write-only
-- configuration. So the load-bearing assertion here is not "the table exists" — it is that the SAME hail, at
-- the SAME age and round, reaches a DIFFERENT outcome in a hive that tuned the knob. That is configurability
-- observable in product behaviour ([[feedback_write_only_index_and_hidden_nav]] — ask who READS it).
--
-- TRUST THRESHOLDS ARE TIGHTEN-ONLY, and that is asserted here too. Per-hive trust knobs are a forgery
-- vector: a hive that could set gold@1 would mint its own gold sellers and the ladder would stop meaning
-- anything platform-wide. A hive may RAISE a bar, never lower it.
begin;

insert into auth.users(id, email) values ('5d000000-0000-4000-8000-00000000000a','tb-a3@gate.local');

do $probe$
declare
  H constant uuid := '084c113b-99c0-45c6-a8e8-b4b8349da46d';
  v text; r int;
begin
  -- 1. AN UNCONFIGURED HIVE IS NOT UNCONFIGURED — it is on the platform defaults.
  raise notice 'RESULT default_instant_ttl=%', public.service_knob(H,'instant_ttl_seconds');
  raise notice 'RESULT default_widen_rounds=%', public.service_knob(H,'broadcast_widen_rounds');

  -- 2. TIGHTEN-ONLY on trust: raising the gold bar is allowed, lowering it is refused.
  insert into public.hive_service_settings(hive_id) values (H);
  begin
    update public.hive_service_settings set tier_gold_sales = 100 where hive_id = H;
    raise notice 'RESULT tighten_gold=%', public.service_knob(H,'tier_gold_sales');
  exception when others then raise notice 'RESULT tighten_gold=BLOCKED'; end;
  begin
    update public.hive_service_settings set tier_gold_sales = 2 where hive_id = H;
    raise notice 'RESULT loosen_gold=ACCEPTED';
  exception when others then raise notice 'RESULT loosen_gold=blocked'; end;

  -- 3. THE KNOB CHANGES PRODUCT BEHAVIOUR. A hail out of rounds under the DEFAULT expires; give the hive
  -- more rounds and the identical hail widens instead. Same row, same age, different outcome.
  update public.hive_service_settings set broadcast_widen_rounds = 4 where hive_id = H;
  insert into public.service_requests(id, client_auth_uid, hive_id, status, mode, custom_scope,
                                      broadcast_round, offer_ttl_expires_at, broadcast_radius_m)
  values ('5d000000-0000-4000-8000-0000000000d1','5d000000-0000-4000-8000-00000000000a',H,
          'broadcasting','instant','TB A3 tuned hail', 2, now() - interval '5 minutes', 5000);

  perform public.sweep_service_broadcasts();
  select status, broadcast_radius_m into v, r from public.service_requests
   where id = '5d000000-0000-4000-8000-0000000000d1'::uuid;
  raise notice 'RESULT tuned_hail_status=%', v;
  raise notice 'RESULT tuned_hail_widened=%', case when r > 5000 then 'yes' else 'NO' end;
end $probe$;

rollback;
