-- ★A QUOTE THE PROVIDER COULD NOT HONOUR, AND THE PROVIDER'S WALLET SENTENCE SHOWN TO THE CLIENT (2026-11-06, GJ M9 J6
-- hop 4: "the client chooses the quote and the work follows").
--
-- Walked: Jericho Bonifacio quoted P5,850 on Ramon Castillo's request from an identity holding P0 in credits. A provider
-- takes a job only while holding 10% of it in credits (guard_accept_requires_reservation), so when Ramon pressed "Choose
-- this provider" the guard refused - and select_quote let its exception through to the CLIENT, whose screen read the
-- provider's own sentence: "You need PHP600 in credits to take a PHP6,000 job (10%), and you have PHP0. Top up to accept
-- it." Ramon has no wallet in this and nothing to top up; the quote was never one the provider could honour.
--
--   1. submit_service_quote refuses a quote its identity cannot hold the reservation for - told to the provider, the one
--      person who can top up ('needs_credits', with the amount and their balance), before any client sees the quote.
--   2. select_quote catches the guard's refusal (a balance spent between quoting and choosing) and answers the client in
--      their own terms ('provider_cannot_take'); the request stays open for another quote.

BEGIN;

CREATE OR REPLACE FUNCTION public.submit_service_quote(p_request_id uuid, p_price numeric, p_eta_minutes integer DEFAULT NULL::integer, p_message text DEFAULT NULL::text, p_provider_id uuid DEFAULT NULL::uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
declare
  v_provider_id uuid;
  v_req public.service_requests%rowtype;
  v_uid uuid;
  v_need numeric;
  v_bal numeric;
begin
  select sp.id into v_provider_id
  from public.service_providers sp
  where sp.id in (select public.my_service_provider_ids())
    and (p_provider_id is null or sp.id = p_provider_id)   -- the identity the person chose, when they hold more than one
  order by sp.verified desc, sp.created_at limit 1;
  if v_provider_id is null then
    return jsonb_build_object('quoted', false, 'reason', 'no_provider_identity');
  end if;
  select r.* into v_req from public.service_requests r where r.id = p_request_id;
  if v_req.id is null or v_req.status <> 'broadcasting' then
    return jsonb_build_object('quoted', false, 'reason', 'not_open');
  end if;
  if v_req.client_auth_uid = auth.uid() then
    return jsonb_build_object('quoted', false, 'reason', 'own_request');
  end if;
  if p_price is null or p_price < 0 then
    return jsonb_build_object('quoted', false, 'reason', 'bad_price');
  end if;
  -- the job's reservation (10%, held when the client chooses this quote - guard_accept_requires_reservation) must be
  -- holdable by the identity that offers it; a quote it cannot honour is refused HERE, to the provider, who can top up
  select sp.auth_uid into v_uid from public.service_providers sp where sp.id = v_provider_id;
  if v_uid is not null then
    v_need := public.listing_reservation_amount(v_req.hive_id, p_price);
    if coalesce(v_need, 0) > 0 then
      v_bal := public.person_credit_balance(v_uid) - coalesce((
          select sum(cr.amount)
            from public.credit_reservations cr
            join public.service_requests sr on sr.id = cr.request_id
            join public.service_providers sp on sp.id = sr.matched_provider_id
           where cr.state = 'held' and cr.request_id is not null and sp.auth_uid = v_uid), 0);
      if v_bal < v_need then
        return jsonb_build_object('quoted', false, 'reason', 'needs_credits', 'need', v_need, 'balance', greatest(v_bal, 0));
      end if;
    end if;
  end if;
  insert into public.service_offers (request_id, provider_id, kind, price, eta_minutes, message)
  values (p_request_id, v_provider_id, 'quote', p_price, p_eta_minutes, p_message)
  on conflict (request_id, provider_id)
  do update set kind = 'quote', price = excluded.price, eta_minutes = excluded.eta_minutes,
                message = excluded.message, status = 'pending', updated_at = now();
  return jsonb_build_object('quoted', true, 'request_id', p_request_id, 'provider_id', v_provider_id);
end $function$;

CREATE OR REPLACE FUNCTION public.select_quote(p_offer_id uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
declare
  v_offer public.service_offers%rowtype;
  v_req public.service_requests%rowtype;
  v_rows integer;
begin
  select o.* into v_offer from public.service_offers o where o.id = p_offer_id;
  if v_offer.id is null or v_offer.kind <> 'quote' or v_offer.status <> 'pending' then
    return jsonb_build_object('selected', false, 'reason', 'offer_not_open');
  end if;
  select r.* into v_req from public.service_requests r where r.id = v_offer.request_id;
  if v_req.client_auth_uid is distinct from auth.uid() then
    return jsonb_build_object('selected', false, 'reason', 'not_your_request');
  end if;

  perform set_config('workhive.service_system_write', 'on', true);

  begin
    update public.service_requests
       set status = 'accepted', matched_provider_id = v_offer.provider_id,
           accepted_at = now(), updated_at = now()
     where id = v_offer.request_id and status = 'broadcasting';
    get diagnostics v_rows = row_count;
  exception when check_violation then
    -- the reservation guard refused: the provider's credits no longer cover the hold. That sentence is the provider's
    -- ("Top up to accept it"); the client is told what it means for THEM, and the job stays open for another quote
    return jsonb_build_object('selected', false, 'reason', 'provider_cannot_take');
  end;
  if v_rows = 0 then
    return jsonb_build_object('selected', false, 'reason', 'request_closed',
                              'status', (select status from public.service_requests where id = v_offer.request_id));
  end if;

  update public.service_offers set status = 'selected', updated_at = now() where id = p_offer_id;
  update public.service_offers set status = 'declined', updated_at = now()
   where request_id = v_offer.request_id and id <> p_offer_id and status = 'pending';
  update public.service_providers set availability = 'on_job', updated_at = now()
   where id = v_offer.provider_id and availability = 'online';

  return jsonb_build_object('selected', true, 'request_id', v_offer.request_id, 'provider_id', v_offer.provider_id);
end $function$;

REVOKE ALL ON FUNCTION public.submit_service_quote(uuid, numeric, integer, text, uuid) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.submit_service_quote(uuid, numeric, integer, text, uuid) TO authenticated, service_role;

COMMIT;
