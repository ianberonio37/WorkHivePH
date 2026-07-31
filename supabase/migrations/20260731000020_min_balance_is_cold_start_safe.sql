-- 20260731000020_min_balance_is_cold_start_safe.sql
--
-- FOUND BY A LIVE TWO-PERSONA WALK, and nothing else would have found it. Migration ...016 made
-- min_list_balance a real deposit (PHP200) and wired the accept gate to it. Correct economics — failure
-- mode 2 of the sustainability study is "the commission is unpayable exactly when it is owed" — but shipped
-- as-is it FROZE THE MARKETPLACE: an ONLINE provider with a 0 balance could accept nothing, and 5 of the 7
-- providers on this platform were in exactly that position. 71% of supply, switched off by a config change.
--
-- WHY NOT JUST GRANT EVERYONE PHP200. Because this session's own solvency gate refuses it, correctly: a
-- grandfather grant is a `voucher_grant`, which is backed by NOTHING, and `vouchers <= commission ever
-- earned` would break instantly (PHP1,000 granted against PHP360 earned). The instrument built earlier
-- today rejected the lazy fix for this one, which is the whole point of having it.
--
-- THE FIX: the deposit applies to providers who have STARTED EARNING, not to a cold start. A provider with
-- no ledger history at all may accept their FIRST job; from then on they carry commission and the deposit
-- applies. This preserves everything the floor was for — an ACTIVE provider is never caught with an empty
-- wallet at completion — without freezing supply or minting a single unbacked credit. It also restores the
-- "cold-start-safe" property the original P6b debt gate was explicitly designed to have and that ...016
-- accidentally removed.
--
-- Farming a fresh provider per job does not pay: the first job still bills commission, which puts the new
-- identity into debt, and the debt gate then blocks it exactly as before.
do $mig$
declare
  v_def text; v_new text;
  v_from constant text :=
    'public.provider_credit_balance(v_provider.id) < public.service_knob(v_req.hive_id, ''min_list_balance'')';
  v_to constant text :=
    'public.provider_credit_balance(v_provider.id) < public.service_knob(v_req.hive_id, ''min_list_balance'')'
    || ' AND EXISTS (SELECT 1 FROM public.service_credit_ledger l'
    || ' WHERE l.account_type = ''provider'' AND l.account_id = v_provider.id)';
begin
  select pg_get_functiondef(oid) into v_def from pg_proc where proname='accept_service_request' limit 1;
  if v_def is null then raise exception 'accept_service_request not found'; end if;
  if position('l.account_type = ''provider''' in v_def) > 0 then
    raise notice 'accept gate is already cold-start-safe - no change'; return;
  end if;
  if position(v_from in v_def) = 0 then
    raise exception 'the min-balance clause was not found; refusing to guess';
  end if;
  v_new := replace(v_def, v_from, v_to);
  execute v_new;
  raise notice 'accept gate is now cold-start-safe: a provider with NO ledger history may take a first job';
end
$mig$;
