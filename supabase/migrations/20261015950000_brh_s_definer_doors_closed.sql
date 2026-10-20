-- BRH-S (2026-10-21): every SECURITY DEFINER function anyone holding the public key may run either asks who is calling,
-- returns only what the platform shows the public, or is closed to the roles that never needed it.
--
-- Supabase's advisor (emailed 2026-10-20) listed 94 definer functions anon could execute; 26 of them checked no caller.
-- Six server-only writers were closed in 20261015500000. Of the other 20, read one by one (callers on every page and
-- edge function, SQL callers, policies and views that use them):
--
--   SIGNED-OUT ENTRY POINTS - a page a visitor opens calls them, and each returns only public facts (declared with their
--   reasons in the definer-doors gate): get_marketplace_price_comps, get_marketplace_seller_public,
--   get_marketplace_trust_badges, listing_reservation_amount, service_knob, service_knob_pct (marketplace.html,
--   marketplace-seller-profile.html), semantic_search_industry_standards, semantic_search_platform_kg_facts (the voice
--   companion's public reference knowledge), check_username_available (sign-up), increment_listing_view (a public listing
--   counts a view), seller_has_published_listing (an anon row policy on marketplace_sellers and the public sellers view).
--
--   SIGNED-IN ONLY - anon goes; authenticated and service_role keep what they had (read first, granted back):
--   marketplace_platform_response_hours (the seller dashboard), provider_credit_balance, service_request_price.
--
--   SERVER-ONLY - no page or edge function calls them and every SQL caller is SECURITY DEFINER, so anon and authenticated
--   go and the service role keeps them: redeem_service_voucher (retired: it only says vouchers are retired),
--   rerank_kb_chunks (a placeholder), service_agreed_base, service_objection_deadline, sync_pm_asset_identity,
--   photo_attach_stats.
--
-- ★TWO OF THEM ANSWERED FOR ANY ID. provider_credit_balance(p_provider_id) and service_request_price(p_request) check no
-- caller, so any signed-in person could read another provider's credit balance or another request's price by naming its
-- id. The pages call them for the person's own provider and the person's own request; they now read through
-- my_provider_credit_balance and my_service_request_price, which answer only for a provider the caller owns or serves
-- (my_service_provider_ids) and a request the caller is a party to. The originals stay for the SECURITY DEFINER functions
-- that call them internally, and are closed to authenticated by 20261021000005, which ships with the pages that stop
-- calling them.

do $$
declare
  r record;
begin
  for r in
    select p.oid::regprocedure as sig,
           has_function_privilege('authenticated', p.oid, 'execute') as auth_had,
           has_function_privilege('service_role', p.oid, 'execute') as svc_had
    from pg_proc p join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public'
      and p.proname in ('marketplace_platform_response_hours', 'provider_credit_balance', 'service_request_price')
  loop
    execute format('revoke execute on function %s from public, anon', r.sig);
    if r.auth_had then
      execute format('grant execute on function %s to authenticated', r.sig);
    end if;
    if r.svc_had then
      execute format('grant execute on function %s to service_role', r.sig);
    end if;
  end loop;

  for r in
    select p.oid::regprocedure as sig
    from pg_proc p join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public'
      and p.proname in ('redeem_service_voucher', 'rerank_kb_chunks', 'service_agreed_base', 'service_objection_deadline',
                        'sync_pm_asset_identity', 'photo_attach_stats')
  loop
    execute format('revoke execute on function %s from public, anon, authenticated', r.sig);
    execute format('grant execute on function %s to service_role', r.sig);
  end loop;
end
$$;

create or replace function public.my_provider_credit_balance(p_provider_id uuid)
returns numeric
language sql
stable
security definer
set search_path = ''
as $$
  select public.provider_credit_balance(p_provider_id)
  where p_provider_id in (select public.my_service_provider_ids());
$$;

revoke all on function public.my_provider_credit_balance(uuid) from public, anon, authenticated;
grant execute on function public.my_provider_credit_balance(uuid) to authenticated, service_role;

create or replace function public.my_service_request_price(p_request uuid)
returns numeric
language sql
stable
security definer
set search_path = ''
as $$
  select public.service_request_price(p_request)
  where exists (
    select 1 from public.service_requests r
    where r.id = p_request
      and (r.client_auth_uid = auth.uid()
           or r.matched_provider_id in (select public.my_service_provider_ids()))
  );
$$;

revoke all on function public.my_service_request_price(uuid) from public, anon, authenticated;
grant execute on function public.my_service_request_price(uuid) to authenticated, service_role;
