-- BRH-S (2026-10-21): provider_credit_balance and service_request_price answered for ANY id they were given, so any
-- signed-in person could read another provider's credit balance or another request's price by naming its id.
--
-- 20261015950000 added the owner-checked reads the pages now use (my_provider_credit_balance, my_service_request_price:
-- a provider the caller owns or serves, a request the caller is a party to) and closed both originals to anon. This
-- closes them to authenticated as well. It ships WITH the page changes that stop calling them (marketplace-seller.html,
-- marketplace.html), so production's pages never call a function they have lost; the SECURITY DEFINER functions that
-- call them internally (accept_service_request, sweep_service_completions, grant_service_reward, the reservation and
-- reward guards, the owner-checked reads themselves) run as their owner and are unaffected.

do $$
declare
  r record;
begin
  for r in
    select p.oid::regprocedure as sig
    from pg_proc p join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public' and p.proname in ('provider_credit_balance', 'service_request_price')
  loop
    execute format('revoke execute on function %s from public, anon, authenticated', r.sig);
    execute format('grant execute on function %s to service_role', r.sig);
  end loop;
end
$$;
