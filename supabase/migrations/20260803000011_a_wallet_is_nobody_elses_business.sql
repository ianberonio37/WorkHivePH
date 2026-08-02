-- seller_credit_balance() took a seller NAME and answered for anyone.
--
-- It is SECURITY DEFINER and EXECUTE defaults to PUBLIC, so any signed-in user could pass a competitor's
-- worker name and read their available and reserved credits. That is commercially sensitive: reserved
-- tells you how much inventory someone has live, and available tells you how much more they can list.
-- Nothing in the marketplace should let one seller size up another's working capital.
--
-- The function has to stay DEFINER — it reads the ledger, which is deliberately not client-readable — so
-- the fix is an explicit party check inside it, exactly as the truth views do. A definer function without
-- an internal party check is an RLS bypass with extra steps.

create or replace function public.seller_credit_balance(p_seller text)
returns table (available numeric, reserved numeric, total numeric)
language plpgsql
stable security definer
set search_path to 'pg_catalog', 'public'
as $function$
declare v_uid uuid := auth.uid();
begin
  -- A wallet is the owner's, or an admin's to audit. Backend/system callers (no JWT) are vetted.
  if v_uid is not null
     and not public.is_marketplace_admin()
     and not exists (select 1 from public.marketplace_sellers
                      where worker_name = p_seller and auth_uid = v_uid)
  then
    raise exception 'A credit balance is only visible to its owner'
      using errcode = '42501';
  end if;

  return query
  with me as (
    select ms.auth_uid from public.marketplace_sellers ms where ms.worker_name = p_seller limit 1
  ), led as (
    select coalesce(sum(l.amount), 0) as bal
      from public.service_credit_ledger l, me
     where l.account_type = 'consumer' and l.account_id = me.auth_uid
  ), res as (
    select coalesce(sum(cr.amount), 0) as held
      from public.credit_reservations cr
     where cr.seller_name = p_seller and cr.state = 'held'
  )
  select (led.bal - res.held)::numeric, res.held::numeric, led.bal::numeric from led, res;
end $function$;

revoke all on function public.seller_credit_balance(text) from public, anon;
grant execute on function public.seller_credit_balance(text) to authenticated, service_role;

-- The starter grant resolves the caller from auth.uid() and takes no arguments, so it is safe to expose
-- and useless to anyone who is not a verified seller.
revoke all on function public.claim_starter_grant() from public, anon;
grant execute on function public.claim_starter_grant() to authenticated, service_role;

comment on function public.seller_credit_balance(text) is
  'Available / reserved / total credits for ONE seller. Party-checked inside the function because it is '
  'SECURITY DEFINER: without the check, any signed-in user could read a competitor''s working capital by '
  'passing their worker name.';
