-- 20260731000019_accept_refusal_states_the_floor.sql
--
-- A refusal a human cannot act on is not a refusal. The accept gate returns `insufficient_credits` with the
-- provider's balance, and the seller UI turned that into "Your credit balance is negative" — which was true
-- while the threshold was `< 0`, and became FALSE the moment mig 20260731000016 made it a real deposit. A
-- provider sitting at +150 is not negative; they were being told something untrue AND not being told the
-- number they actually needed to clear.
--
-- So the payload now carries the FLOOR alongside the balance. The UI can then say "you have PHP150,
-- accepting needs PHP200" instead of guessing, and if a hive tightens its own floor the message follows
-- automatically rather than drifting back into a lie.
do $mig$
declare
  v_def text; v_new text;
  v_from constant text :=
    '''insufficient_credits'',
                              ''balance'', public.provider_credit_balance(v_provider.id)';
begin
  select pg_get_functiondef(oid) into v_def from pg_proc where proname='accept_service_request' limit 1;
  if v_def is null then raise exception 'accept_service_request not found'; end if;
  if position('min_balance' in v_def) > 0 then
    raise notice 'accept refusal already carries min_balance - no change'; return;
  end if;
  -- Anchor on the balance term only; whitespace inside the jsonb_build_object call is not something to
  -- guess at, and a failed match must RAISE rather than silently leave the misleading message in place.
  if position('''balance'', public.provider_credit_balance(v_provider.id)' in v_def) = 0 then
    raise exception 'the insufficient_credits payload was not found; refusing to guess';
  end if;
  v_new := replace(v_def,
    '''balance'', public.provider_credit_balance(v_provider.id)',
    '''balance'', public.provider_credit_balance(v_provider.id), '
    || '''min_balance'', public.service_knob(v_req.hive_id, ''min_list_balance'')');
  execute v_new;
  raise notice 'accept refusal now states the floor as well as the balance';
end
$mig$;
