-- ★A PERSON WITH TWO PROVIDER IDENTITIES COULD NOT SAY WHICH ONE WAS ANSWERING (2026-11-06, GJ M9 J6 hop 3: "the
-- provider's quote is on the client's request to choose").
--
-- A hive's members are its field crew by design (my_service_provider_ids: a person's own provider rows, plus the hive
-- team of every hive they are an active member of), so a member who also runs their own business holds two identities.
-- submit_service_quote and accept_service_request then picked one for them - `order by verified desc, created_at` - and
-- the console never said which. Walked: Jericho Bonifacio quoted from his console and the client read the quote as
-- "Manila Electronics Assembly Field Services" (his hive's verified team), not his own "Jericho Bonifacio Appliance
-- Repair". The price, the obligation and the review that follows were all put under a name he never chose.
--
-- Both functions take an optional p_provider_id: when given it must be one of the caller's own identities (the same
-- my_service_provider_ids() gate, nothing wider); when absent the old order stands, so every existing call is unchanged.
-- The old signatures are DROPPED first - adding a parameter by CREATE OR REPLACE makes an overload, and two candidates
-- for one call is PGRST203 on every call. Execute is the signed-in roles' only (anon held it by default and has no
-- provider identity to act with).

BEGIN;

DROP FUNCTION IF EXISTS public.submit_service_quote(uuid, numeric, integer, text);
DROP FUNCTION IF EXISTS public.accept_service_request(uuid, integer);

CREATE OR REPLACE FUNCTION public.submit_service_quote(p_request_id uuid, p_price numeric, p_eta_minutes integer DEFAULT NULL::integer, p_message text DEFAULT NULL::text, p_provider_id uuid DEFAULT NULL::uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
declare
  v_provider_id uuid;
  v_req public.service_requests%rowtype;
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
  insert into public.service_offers (request_id, provider_id, kind, price, eta_minutes, message)
  values (p_request_id, v_provider_id, 'quote', p_price, p_eta_minutes, p_message)
  on conflict (request_id, provider_id)
  do update set kind = 'quote', price = excluded.price, eta_minutes = excluded.eta_minutes,
                message = excluded.message, status = 'pending', updated_at = now();
  return jsonb_build_object('quoted', true, 'request_id', p_request_id, 'provider_id', v_provider_id);
end $function$;

CREATE OR REPLACE FUNCTION public.accept_service_request(p_request_id uuid, p_eta_minutes integer DEFAULT NULL::integer, p_provider_id uuid DEFAULT NULL::uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public', 'extensions'
AS $function$
declare
  v_provider public.service_providers%rowtype;
  v_req public.service_requests%rowtype;
  v_won boolean;
  v_cert_cat text;
  v_cert_level integer;
begin
  -- caller must own an ONLINE provider identity
  select sp.* into v_provider
  from public.service_providers sp
  where sp.id in (select public.my_service_provider_ids())
    and (p_provider_id is null or sp.id = p_provider_id)   -- the identity the person chose, when they hold more than one
    and sp.availability = 'online'
  order by sp.verified desc, sp.created_at
  limit 1;
  if v_provider.id is null then
    return jsonb_build_object('accepted', false, 'reason', 'no_online_provider_identity');
  end if;

  select r.* into v_req from public.service_requests r where r.id = p_request_id;
  if v_req.id is null then
    return jsonb_build_object('accepted', false, 'reason', 'not_found');
  end if;
  if v_req.client_auth_uid = auth.uid() then
    return jsonb_build_object('accepted', false, 'reason', 'own_request');
  end if;
  -- eligibility: category overlap (catalog requests) + radius when both points exist
  if v_req.catalog_item_id is not null and not exists (
    select 1 from public.service_catalog c
    where c.id = v_req.catalog_item_id
      and (c.category = any (v_provider.categories))
  ) then
    return jsonb_build_object('accepted', false, 'reason', 'category_mismatch');
  end if;
  if v_req.location is not null and v_provider.base_location is not null
     and not st_dwithin(v_req.location, v_provider.base_location, v_req.broadcast_radius_m * 4) then
    return jsonb_build_object('accepted', false, 'reason', 'out_of_radius');
  end if;

  -- J20 CERTIFIED-SKILL GATE: a premium trade needs an EARNED badge, not a self-declared
  -- categories[] entry. Checked after category overlap (so the message is the specific one) and
  -- before the money gate. Open categories have requires_cert_level NULL and skip this entirely.
  if v_req.catalog_item_id is not null then
    select c.category, c.requires_cert_level into v_cert_cat, v_cert_level
      from public.service_catalog c where c.id = v_req.catalog_item_id;
    if v_cert_level is not null
       and not public.provider_is_certified_for(v_provider.id, v_cert_cat, v_cert_level) then
      return jsonb_build_object('accepted', false, 'reason', 'not_certified',
                                'category', v_cert_cat, 'required_level', v_cert_level);
    end if;
  end if;

  -- P6b (mig 48 adjunct): a provider in commission DEBT cannot accept until they top up
  if public.provider_credit_balance(v_provider.id) < public.service_knob(v_req.hive_id, 'min_list_balance') AND EXISTS (SELECT 1 FROM public.service_credit_ledger l WHERE l.account_type = 'provider' AND l.account_id = v_provider.id) then
    return jsonb_build_object('accepted', false, 'reason', 'insufficient_credits',
                              'balance', public.provider_credit_balance(v_provider.id), 'min_balance', public.service_knob(v_req.hive_id, 'min_list_balance'));
  end if;

  -- announce to the state-machine guard for THIS transaction only
  perform set_config('workhive.service_system_write', 'on', true);

  -- ★ the atomic race: exactly one caller flips broadcasting -> accepted
  update public.service_requests
     set status = 'accepted',
         matched_provider_id = v_provider.id,
         accepted_at = now(),
         updated_at = now()
   where id = p_request_id
     and status = 'broadcasting';
  v_won := found;

  if not v_won then
    -- 0 rows = lost the race (or state moved) — surfaced honestly, never silently
    return jsonb_build_object('accepted', false, 'reason', 'lost_race_or_closed',
                              'status', (select status from public.service_requests where id = p_request_id));
  end if;

  -- record the winning accept; expire other pending instant-accepts
  insert into public.service_offers (request_id, provider_id, kind, eta_minutes, status)
  values (p_request_id, v_provider.id, 'accept', p_eta_minutes, 'selected')
  on conflict (request_id, provider_id)
  do update set kind = 'accept', status = 'selected', eta_minutes = excluded.eta_minutes, updated_at = now();
  update public.service_offers
     set status = 'expired', updated_at = now()
   where request_id = p_request_id and provider_id <> v_provider.id and status = 'pending' and kind = 'accept';

  -- availability follows the job (mirrors the sync trigger for direct RPC path)
  update public.service_providers set availability = 'on_job', updated_at = now()
   where id = v_provider.id and availability = 'online';

  return jsonb_build_object('accepted', true, 'request_id', p_request_id, 'provider_id', v_provider.id);
end $function$;

REVOKE ALL ON FUNCTION public.submit_service_quote(uuid, numeric, integer, text, uuid) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.submit_service_quote(uuid, numeric, integer, text, uuid) TO authenticated, service_role;
REVOKE ALL ON FUNCTION public.accept_service_request(uuid, integer, uuid) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.accept_service_request(uuid, integer, uuid) TO authenticated, service_role;

COMMIT;
